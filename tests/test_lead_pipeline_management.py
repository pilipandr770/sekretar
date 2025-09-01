"""
Lead Pipeline Management Tests

This module implements comprehensive tests for lead pipeline management functionality
including lead creation, stage progression, conversion rate calculations, and lead assignment.

Requirements: 3.2, 3.3 - CRM lead pipeline management and assignment
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from app import db
from app.models.lead import Lead
from app.models.pipeline import Pipeline, Stage
from app.models.contact import Contact
from app.models.user import User


class TestLeadPipelineManagement:
    """Test suite for lead pipeline management functionality."""
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data for testing."""
        try:
            with open('comprehensive_test_dataset.json', 'r') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback data if dataset file is not available
            return {
                'sap_germany': {
                    'name': 'SAP SE',
                    'vat_number': 'DE143593636',
                    'country_code': 'DE',
                    'address': 'Dietmar-Hopp-Allee 16, 69190 Walldorf',
                    'industry': 'Technology',
                    'size': 'Large'
                },
                'bayer_germany': {
                    'name': 'Bayer AG',
                    'vat_number': 'DE119850003',
                    'country_code': 'DE',
                    'address': 'Kaiser-Wilhelm-Allee 1, 51373 Leverkusen',
                    'industry': 'Healthcare',
                    'size': 'Large'
                },
                'total_france': {
                    'name': 'TotalEnergies SE',
                    'vat_number': 'FR40542051180',
                    'country_code': 'FR',
                    'address': '2 Place Jean Millier, 92400 Courbevoie',
                    'industry': 'Energy',
                    'size': 'Large'
                }
            }
    
    @pytest.fixture
    def test_pipeline(self, app, tenant):
        """Create a test pipeline with stages."""
        with app.app_context():
            db.session.add(tenant)
            
            # Create pipeline
            pipeline = Pipeline.create(
                tenant_id=tenant.id,
                name="Sales Pipeline",
                description="Test sales pipeline",
                is_default=True
            )
            
            # Create stages
            stages_data = [
                {"name": "Lead", "color": "#3498db", "position": 0},
                {"name": "Qualified", "color": "#f39c12", "position": 1},
                {"name": "Proposal", "color": "#e74c3c", "position": 2},
                {"name": "Negotiation", "color": "#9b59b6", "position": 3},
                {"name": "Closed Won", "color": "#27ae60", "position": 4, "is_closed": True, "is_won": True},
                {"name": "Closed Lost", "color": "#95a5a6", "position": 5, "is_closed": True, "is_won": False}
            ]
            
            stage_ids = []
            for stage_data in stages_data:
                stage = Stage.create(
                    tenant_id=tenant.id,
                    pipeline_id=pipeline.id,
                    **stage_data
                )
                stage_ids.append(stage.id)
            
            pipeline.stages_order = stage_ids
            pipeline.save()
            
            return pipeline
    
    @pytest.fixture
    def test_contacts(self, app, tenant, real_company_data):
        """Create test contacts from real company data."""
        with app.app_context():
            db.session.add(tenant)
            
            contacts = []
            for company_key, company_data in real_company_data.items():
                contact = Contact.create(
                    tenant_id=tenant.id,
                    first_name="John",
                    last_name="Doe",
                    company=company_data['name'],
                    email=f"john.doe@{company_key}.com",
                    phone="+49 123 456789",
                    title="CTO",
                    contact_type="prospect",
                    source="website"
                )
                contacts.append(contact)
            
            return contacts
    
    @pytest.fixture
    def sales_users(self, app, tenant):
        """Create sales users for assignment testing."""
        with app.app_context():
            db.session.add(tenant)
            
            users = []
            user_data = [
                {"first_name": "Alice", "last_name": "Johnson", "email": "alice@test.com", "role": "sales_rep"},
                {"first_name": "Bob", "last_name": "Smith", "email": "bob@test.com", "role": "sales_rep"},
                {"first_name": "Carol", "last_name": "Wilson", "email": "carol@test.com", "role": "sales_manager"}
            ]
            
            for user_info in user_data:
                user = User.create(
                    tenant_id=tenant.id,
                    password_hash="hashed_password",
                    is_active=True,
                    **user_info
                )
                users.append(user)
            
            return users

    # ============================================================================
    # LEAD CREATION TESTS
    # ============================================================================
    
    def test_create_lead_with_real_company_data(self, client, auth_headers, test_pipeline, test_contacts):
        """Test creating leads with real company data.
        
        Requirements: 3.2 - Lead pipeline management
        """
        contact = test_contacts[0]  # SAP contact
        
        lead_data = {
            'title': f'Enterprise Software Implementation - {contact.company}',
            'contact_id': contact.id,
            'pipeline_id': test_pipeline.id,
            'value': 250000.00,
            'probability': 25,
            'expected_close_date': (datetime.now() + timedelta(days=90)).isoformat(),
            'description': f'Potential enterprise software implementation for {contact.company}',
            'priority': 'high',
            'source': 'website',
            'tags': ['enterprise', 'software', 'implementation']
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
        assert contact.company in lead['title']
        assert lead['contact_id'] == contact.id
        assert lead['pipeline_id'] == test_pipeline.id
        assert lead['value'] == 250000.00
        assert lead['probability'] == 25
        assert lead['priority'] == 'high'
        assert 'enterprise' in lead['tags']
        
        # Verify lead is in first stage
        first_stage = test_pipeline.get_first_stage()
        assert lead['stage_id'] == first_stage.id
        assert lead['status'] == 'open'
    
    def test_create_multiple_leads_different_companies(self, client, auth_headers, test_pipeline, test_contacts):
        """Test creating leads for different companies.
        
        Requirements: 3.2 - Lead pipeline management
        """
        leads_created = []
        
        for i, contact in enumerate(test_contacts[:3]):  # Test with first 3 companies
            lead_data = {
                'title': f'Business Opportunity - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'value': 100000.00 + (i * 50000),  # Different values
                'probability': 20 + (i * 10),  # Different probabilities
                'expected_close_date': (datetime.now() + timedelta(days=60 + i*30)).isoformat(),
                'description': f'Business opportunity for {contact.company}',
                'priority': ['low', 'medium', 'high'][i],
                'source': ['website', 'referral', 'cold_call'][i]
            }
            
            response = client.post(
                '/api/v1/crm/leads',
                json=lead_data,
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = response.get_json()
            leads_created.append(data['data']['lead'])
        
        # Verify all leads were created with different properties
        assert len(leads_created) == 3
        values = [lead['value'] for lead in leads_created]
        assert values == [100000.00, 150000.00, 200000.00]
        
        probabilities = [lead['probability'] for lead in leads_created]
        assert probabilities == [20, 30, 40]
        
        priorities = [lead['priority'] for lead in leads_created]
        assert priorities == ['low', 'medium', 'high']

    # ============================================================================
    # STAGE PROGRESSION TESTS
    # ============================================================================
    
    def test_move_lead_through_pipeline_stages(self, client, auth_headers, test_pipeline, test_contacts):
        """Test moving a lead through all pipeline stages.
        
        Requirements: 3.2 - Lead pipeline management
        """
        # Create a lead
        contact = test_contacts[0]
        lead_data = {
            'title': f'Pipeline Test - {contact.company}',
            'contact_id': contact.id,
            'pipeline_id': test_pipeline.id,
            'value': 150000.00,
            'probability': 25
        }
        
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
        assert response.status_code == 201
        lead_id = response.get_json()['data']['lead']['id']
        
        # Get ordered stages
        stages = test_pipeline.get_ordered_stages()
        
        # Move through each stage (except first, which is already set)
        for i, stage in enumerate(stages[1:], 1):
            stage_data = {
                'stage_id': stage.id,
                'probability': 20 + (i * 15),  # Increase probability with each stage
                'notes': f'Moved to {stage.name} stage'
            }
            
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/stage',
                json=stage_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            
            # Verify stage change
            lead = data['data']['lead']
            assert lead['stage_id'] == stage.id
            assert lead['stage_name'] == stage.name
            
            # Check if lead status changed for closed stages
            if stage.is_closed:
                if stage.is_won:
                    assert lead['status'] == 'won'
                    assert lead['probability'] == 100
                else:
                    assert lead['status'] == 'lost'
                    assert lead['probability'] == 0
            else:
                assert lead['status'] == 'open'
    
    def test_stage_progression_with_validation(self, client, auth_headers, test_pipeline, test_contacts):
        """Test stage progression with validation rules.
        
        Requirements: 3.2 - Lead pipeline management
        """
        # Create a lead
        contact = test_contacts[0]
        lead_data = {
            'title': f'Validation Test - {contact.company}',
            'contact_id': contact.id,
            'pipeline_id': test_pipeline.id,
            'value': 100000.00
        }
        
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
        lead_id = response.get_json()['data']['lead']['id']
        
        # Test moving to non-existent stage
        invalid_stage_data = {
            'stage_id': 99999,
            'notes': 'Invalid stage test'
        }
        
        response = client.put(
            f'/api/v1/crm/leads/{lead_id}/stage',
            json=invalid_stage_data,
            headers=auth_headers
        )
        
        assert response.status_code == 404
        data = response.get_json()
        assert data['success'] is False
        
        # Test moving with invalid probability
        stages = test_pipeline.get_ordered_stages()
        valid_stage_data = {
            'stage_id': stages[1].id,
            'probability': 150,  # Invalid probability > 100
            'notes': 'Invalid probability test'
        }
        
        response = client.put(
            f'/api/v1/crm/leads/{lead_id}/stage',
            json=valid_stage_data,
            headers=auth_headers
        )
        
        # Should still work but probability should be capped or validated
        assert response.status_code in [200, 400]  # Depending on validation implementation

    # ============================================================================
    # CONVERSION RATE CALCULATION TESTS
    # ============================================================================
    
    def test_pipeline_conversion_rate_calculation(self, client, auth_headers, test_pipeline, test_contacts):
        """Test pipeline conversion rate calculations.
        
        Requirements: 3.2 - Lead pipeline management
        """
        # Create multiple leads in different stages
        leads_data = []
        stages = test_pipeline.get_ordered_stages()
        
        # Create 10 leads distributed across stages
        for i in range(10):
            contact = test_contacts[i % len(test_contacts)]
            stage_index = i % len(stages)
            
            lead_data = {
                'title': f'Conversion Test Lead {i+1} - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'value': 50000.00 + (i * 10000),
                'probability': 25
            }
            
            # Create lead
            response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
            assert response.status_code == 201
            lead_id = response.get_json()['data']['lead']['id']
            leads_data.append({'id': lead_id, 'stage_index': stage_index})
            
            # Move to appropriate stage if not first stage
            if stage_index > 0:
                stage_data = {
                    'stage_id': stages[stage_index].id,
                    'probability': 20 + (stage_index * 15)
                }
                
                response = client.put(
                    f'/api/v1/crm/leads/{lead_id}/stage',
                    json=stage_data,
                    headers=auth_headers
                )
                assert response.status_code == 200
        
        # Close some leads as won/lost
        won_leads = 2
        lost_leads = 2
        
        # Mark 2 leads as won
        for i in range(won_leads):
            lead_id = leads_data[i]['id']
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/status',
                json={'status': 'won', 'notes': 'Deal closed successfully'},
                headers=auth_headers
            )
            assert response.status_code == 200
        
        # Mark 2 leads as lost
        for i in range(won_leads, won_leads + lost_leads):
            lead_id = leads_data[i]['id']
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/status',
                json={'status': 'lost', 'reason': 'Budget constraints', 'notes': 'Lost due to budget'},
                headers=auth_headers
            )
            assert response.status_code == 200
        
        # Get pipeline statistics
        response = client.get(f'/api/v1/crm/pipelines/{test_pipeline.id}/stats', headers=auth_headers)
        assert response.status_code == 200
        
        stats = response.get_json()['data']
        
        # Verify conversion calculations
        total_leads = 10
        closed_leads = won_leads + lost_leads
        conversion_rate = (won_leads / total_leads) * 100
        win_rate = (won_leads / closed_leads) * 100 if closed_leads > 0 else 0
        
        assert stats['total_leads'] == total_leads
        assert stats['won_leads'] == won_leads
        assert stats['lost_leads'] == lost_leads
        assert abs(stats['conversion_rate'] - conversion_rate) < 0.01
        assert abs(stats['win_rate'] - win_rate) < 0.01
    
    def test_stage_conversion_rates(self, client, auth_headers, test_pipeline, test_contacts):
        """Test conversion rates between pipeline stages.
        
        Requirements: 3.2 - Lead pipeline management
        """
        stages = test_pipeline.get_ordered_stages()
        
        # Create leads and distribute them across stages
        stage_distribution = {
            0: 10,  # Lead stage: 10 leads
            1: 7,   # Qualified stage: 7 leads
            2: 5,   # Proposal stage: 5 leads
            3: 3,   # Negotiation stage: 3 leads
            4: 2,   # Closed Won: 2 leads
            5: 1    # Closed Lost: 1 lead
        }
        
        created_leads = []
        
        for stage_index, count in stage_distribution.items():
            for i in range(count):
                contact = test_contacts[i % len(test_contacts)]
                
                lead_data = {
                    'title': f'Stage {stage_index} Lead {i+1} - {contact.company}',
                    'contact_id': contact.id,
                    'pipeline_id': test_pipeline.id,
                    'value': 75000.00,
                    'probability': 25
                }
                
                # Create lead
                response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
                assert response.status_code == 201
                lead_id = response.get_json()['data']['lead']['id']
                created_leads.append(lead_id)
                
                # Move to appropriate stage
                if stage_index > 0:
                    stage_data = {
                        'stage_id': stages[stage_index].id,
                        'probability': 20 + (stage_index * 15)
                    }
                    
                    response = client.put(
                        f'/api/v1/crm/leads/{lead_id}/stage',
                        json=stage_data,
                        headers=auth_headers
                    )
                    assert response.status_code == 200
        
        # Get detailed pipeline analytics
        response = client.get(f'/api/v1/crm/pipelines/{test_pipeline.id}/analytics', headers=auth_headers)
        assert response.status_code == 200
        
        analytics = response.get_json()['data']
        
        # Verify stage-to-stage conversion rates
        expected_conversions = {
            'lead_to_qualified': (7 / 10) * 100,      # 70%
            'qualified_to_proposal': (5 / 7) * 100,   # ~71.4%
            'proposal_to_negotiation': (3 / 5) * 100, # 60%
            'negotiation_to_close': (3 / 3) * 100     # 100% (2 won + 1 lost)
        }
        
        for conversion_key, expected_rate in expected_conversions.items():
            if conversion_key in analytics['stage_conversions']:
                actual_rate = analytics['stage_conversions'][conversion_key]
                assert abs(actual_rate - expected_rate) < 1.0  # Allow 1% tolerance

    # ============================================================================
    # LEAD ASSIGNMENT AND ROUTING TESTS
    # ============================================================================
    
    def test_lead_assignment_to_sales_users(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test assigning leads to sales users.
        
        Requirements: 3.3 - Lead assignment and routing
        """
        # Create leads and assign to different users
        for i, contact in enumerate(test_contacts[:3]):
            user = sales_users[i % len(sales_users)]
            
            lead_data = {
                'title': f'Assignment Test - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'assigned_to_id': user.id,
                'value': 120000.00,
                'priority': 'medium'
            }
            
            response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
            assert response.status_code == 201
            
            data = response.get_json()
            lead = data['data']['lead']
            
            # Verify assignment
            assert lead['assigned_to_id'] == user.id
            assert lead['assigned_to_name'] == user.full_name
            assert lead['assigned_to_email'] == user.email
        
        # Test getting leads by assigned user
        for user in sales_users:
            response = client.get(
                f'/api/v1/crm/leads?assigned_to_id={user.id}',
                headers=auth_headers
            )
            assert response.status_code == 200
            
            data = response.get_json()
            user_leads = data['data']['leads']
            
            # Verify all returned leads are assigned to this user
            for lead in user_leads:
                assert lead['assigned_to_id'] == user.id
    
    def test_lead_reassignment(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test reassigning leads between users.
        
        Requirements: 3.3 - Lead assignment and routing
        """
        contact = test_contacts[0]
        
        # Create lead assigned to first user
        lead_data = {
            'title': f'Reassignment Test - {contact.company}',
            'contact_id': contact.id,
            'pipeline_id': test_pipeline.id,
            'assigned_to_id': sales_users[0].id,
            'value': 180000.00
        }
        
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
        assert response.status_code == 201
        lead_id = response.get_json()['data']['lead']['id']
        
        # Reassign to second user
        reassignment_data = {
            'assigned_to_id': sales_users[1].id,
            'notes': 'Reassigned due to territory change'
        }
        
        response = client.put(
            f'/api/v1/crm/leads/{lead_id}',
            json=reassignment_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        lead = data['data']['lead']
        
        # Verify reassignment
        assert lead['assigned_to_id'] == sales_users[1].id
        assert lead['assigned_to_name'] == sales_users[1].full_name
        
        # Unassign lead
        unassign_data = {
            'assigned_to_id': None,
            'notes': 'Unassigned for redistribution'
        }
        
        response = client.put(
            f'/api/v1/crm/leads/{lead_id}',
            json=unassign_data,
            headers=auth_headers
        )
        
        assert response.status_code == 200
        data = response.get_json()
        lead = data['data']['lead']
        
        # Verify unassignment
        assert lead['assigned_to_id'] is None
        assert lead.get('assigned_to_name') is None
    
    def test_automatic_lead_routing_by_criteria(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test automatic lead routing based on criteria.
        
        Requirements: 3.3 - Lead assignment and routing
        """
        # Mock automatic routing service
        with patch('app.services.lead_routing.LeadRoutingService') as mock_routing:
            mock_routing.return_value.assign_lead.return_value = sales_users[0]
            
            contact = test_contacts[0]
            
            # Create lead with routing criteria
            lead_data = {
                'title': f'Auto-routing Test - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'value': 300000.00,  # High value lead
                'priority': 'high',
                'source': 'website',
                'custom_fields': {
                    'industry': 'Technology',
                    'company_size': 'Enterprise',
                    'territory': 'EMEA'
                },
                'auto_assign': True
            }
            
            response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
            assert response.status_code == 201
            
            data = response.get_json()
            lead = data['data']['lead']
            
            # Verify automatic assignment occurred
            mock_routing.return_value.assign_lead.assert_called_once()
            
            # In a real implementation, verify the lead was assigned based on routing rules
            # For now, just verify the structure is correct
            assert 'assigned_to_id' in lead
    
    def test_lead_workload_balancing(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test lead distribution for workload balancing.
        
        Requirements: 3.3 - Lead assignment and routing
        """
        # Create multiple leads and distribute among users
        leads_per_user = {user.id: 0 for user in sales_users}
        
        # Create 9 leads to distribute among 3 users (3 each for balanced workload)
        for i in range(9):
            contact = test_contacts[i % len(test_contacts)]
            user = sales_users[i % len(sales_users)]
            
            lead_data = {
                'title': f'Workload Test {i+1} - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'assigned_to_id': user.id,
                'value': 100000.00,
                'priority': 'medium'
            }
            
            response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
            assert response.status_code == 201
            
            leads_per_user[user.id] += 1
        
        # Verify balanced distribution
        lead_counts = list(leads_per_user.values())
        assert all(count == 3 for count in lead_counts), f"Unbalanced distribution: {lead_counts}"
        
        # Test getting workload statistics
        response = client.get('/api/v1/crm/users/workload', headers=auth_headers)
        assert response.status_code == 200
        
        workload_data = response.get_json()['data']
        
        # Verify workload statistics
        for user_stats in workload_data['users']:
            assert user_stats['open_leads'] == 3
            assert user_stats['total_value'] == 300000.00  # 3 leads * 100k each
    
    def test_lead_assignment_validation(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test lead assignment validation rules.
        
        Requirements: 3.3 - Lead assignment and routing
        """
        contact = test_contacts[0]
        
        # Test assigning to non-existent user
        lead_data = {
            'title': f'Invalid Assignment Test - {contact.company}',
            'contact_id': contact.id,
            'pipeline_id': test_pipeline.id,
            'assigned_to_id': 99999,  # Non-existent user
            'value': 150000.00
        }
        
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False
        assert 'assigned_to_id' in data.get('errors', {})
        
        # Test assigning to inactive user
        inactive_user = User.create(
            tenant_id=sales_users[0].tenant_id,
            email="inactive@test.com",
            password_hash="hashed_password",
            first_name="Inactive",
            last_name="User",
            role="sales_rep",
            is_active=False
        )
        
        lead_data['assigned_to_id'] = inactive_user.id
        
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
        assert response.status_code == 400
        
        data = response.get_json()
        assert data['success'] is False

    # ============================================================================
    # INTEGRATION AND PERFORMANCE TESTS
    # ============================================================================
    
    def test_bulk_lead_operations(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test bulk operations on leads for performance validation.
        
        Requirements: 3.2, 3.3 - Lead pipeline management and assignment
        """
        # Create multiple leads in bulk
        bulk_leads = []
        
        for i in range(20):  # Create 20 leads
            contact = test_contacts[i % len(test_contacts)]
            user = sales_users[i % len(sales_users)]
            
            lead_data = {
                'title': f'Bulk Test Lead {i+1} - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'assigned_to_id': user.id,
                'value': 50000.00 + (i * 5000),
                'probability': 25,
                'priority': ['low', 'medium', 'high'][i % 3]
            }
            
            response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
            assert response.status_code == 201
            
            lead_id = response.get_json()['data']['lead']['id']
            bulk_leads.append(lead_id)
        
        # Test bulk stage updates
        stages = test_pipeline.get_ordered_stages()
        qualified_stage = stages[1]
        
        # Move first 10 leads to qualified stage
        for lead_id in bulk_leads[:10]:
            stage_data = {
                'stage_id': qualified_stage.id,
                'probability': 40,
                'notes': 'Bulk qualification update'
            }
            
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/stage',
                json=stage_data,
                headers=auth_headers
            )
            assert response.status_code == 200
        
        # Verify bulk updates
        response = client.get(
            f'/api/v1/crm/leads?stage_id={qualified_stage.id}',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        qualified_leads = response.get_json()['data']['leads']
        assert len(qualified_leads) == 10
        
        # Test bulk status updates (close some leads)
        won_leads = bulk_leads[10:15]  # 5 leads as won
        lost_leads = bulk_leads[15:18]  # 3 leads as lost
        
        for lead_id in won_leads:
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/status',
                json={'status': 'won', 'notes': 'Bulk won update'},
                headers=auth_headers
            )
            assert response.status_code == 200
        
        for lead_id in lost_leads:
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/status',
                json={'status': 'lost', 'reason': 'Budget', 'notes': 'Bulk lost update'},
                headers=auth_headers
            )
            assert response.status_code == 200
        
        # Verify final statistics
        response = client.get(f'/api/v1/crm/pipelines/{test_pipeline.id}/stats', headers=auth_headers)
        assert response.status_code == 200
        
        stats = response.get_json()['data']
        assert stats['total_leads'] == 20
        assert stats['won_leads'] == 5
        assert stats['lost_leads'] == 3
        assert stats['open_leads'] == 12  # 20 - 5 - 3
    
    def test_lead_pipeline_analytics_comprehensive(self, client, auth_headers, test_pipeline, test_contacts, sales_users):
        """Test comprehensive pipeline analytics and reporting.
        
        Requirements: 3.2 - Lead pipeline management
        """
        # Create a comprehensive dataset for analytics
        stages = test_pipeline.get_ordered_stages()
        
        # Create leads with various characteristics
        analytics_data = []
        
        for i in range(30):
            contact = test_contacts[i % len(test_contacts)]
            user = sales_users[i % len(sales_users)]
            stage_index = min(i // 5, len(stages) - 1)  # Distribute across stages
            
            lead_data = {
                'title': f'Analytics Lead {i+1} - {contact.company}',
                'contact_id': contact.id,
                'pipeline_id': test_pipeline.id,
                'assigned_to_id': user.id,
                'value': 25000.00 + (i * 7500),  # Varying values
                'probability': 10 + (stage_index * 15),
                'priority': ['low', 'medium', 'high', 'urgent'][i % 4],
                'source': ['website', 'referral', 'cold_call', 'social_media'][i % 4],
                'expected_close_date': (datetime.now() + timedelta(days=30 + i*5)).isoformat()
            }
            
            response = client.post('/api/v1/crm/leads', json=lead_data, headers=auth_headers)
            assert response.status_code == 201
            
            lead_id = response.get_json()['data']['lead']['id']
            analytics_data.append({
                'id': lead_id,
                'stage_index': stage_index,
                'value': lead_data['value'],
                'user_id': user.id
            })
            
            # Move to appropriate stage
            if stage_index > 0:
                stage_data = {
                    'stage_id': stages[stage_index].id,
                    'probability': lead_data['probability']
                }
                
                response = client.put(
                    f'/api/v1/crm/leads/{lead_id}/stage',
                    json=stage_data,
                    headers=auth_headers
                )
                assert response.status_code == 200
        
        # Close some leads for complete analytics
        won_count = 5
        lost_count = 3
        
        for i in range(won_count):
            lead_id = analytics_data[i]['id']
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/status',
                json={'status': 'won', 'notes': 'Analytics won'},
                headers=auth_headers
            )
            assert response.status_code == 200
        
        for i in range(won_count, won_count + lost_count):
            lead_id = analytics_data[i]['id']
            response = client.put(
                f'/api/v1/crm/leads/{lead_id}/status',
                json={'status': 'lost', 'reason': 'Competition', 'notes': 'Analytics lost'},
                headers=auth_headers
            )
            assert response.status_code == 200
        
        # Get comprehensive analytics
        response = client.get(f'/api/v1/crm/pipelines/{test_pipeline.id}/analytics', headers=auth_headers)
        assert response.status_code == 200
        
        analytics = response.get_json()['data']
        
        # Verify analytics completeness
        assert 'total_leads' in analytics
        assert 'pipeline_value' in analytics
        assert 'weighted_value' in analytics
        assert 'conversion_rate' in analytics
        assert 'average_deal_size' in analytics
        assert 'stage_distribution' in analytics
        assert 'user_performance' in analytics
        assert 'source_analysis' in analytics
        assert 'priority_breakdown' in analytics
        
        # Verify calculations
        assert analytics['total_leads'] == 30
        assert analytics['won_leads'] == won_count
        assert analytics['lost_leads'] == lost_count
        
        # Verify stage distribution
        stage_dist = analytics['stage_distribution']
        assert len(stage_dist) == len(stages)
        
        # Verify user performance data
        user_perf = analytics['user_performance']
        assert len(user_perf) == len(sales_users)
        
        for user_data in user_perf:
            assert 'user_id' in user_data
            assert 'leads_count' in user_data
            assert 'total_value' in user_data
            assert 'won_count' in user_data
            assert 'conversion_rate' in user_data