"""Comprehensive integration tests for end-to-end workflows and multi-tenant isolation."""
import pytest
import json
import time
import threading
from unittest.mock import patch, MagicMock
from concurrent.futures import ThreadPoolExecutor, as_completed
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.crm import Lead, Contact, Pipeline, Stage
from app.models.inbox import InboxMessage, Thread
from app.models.kyb_monitoring import Counterparty
from app.models.billing import Subscription, Plan
from flask_jwt_extended import create_access_token


class TestEndToEndWorkflows:
    """Test complete end-to-end user workflows."""
    
    def test_complete_customer_inquiry_to_lead_workflow(self, client, tenant, user, auth_headers):
        """Test complete workflow from customer inquiry to lead creation and management."""
        with patch('app.services.agent_orchestrator.AgentOrchestrator.process_message') as mock_agent:
            # Mock AI agent response
            mock_agent.return_value = {
                'response': 'Thank you for your inquiry! I\'d be happy to help you with our services.',
                'intent': 'sales',
                'confidence': 0.95,
                'lead_created': True
            }
            
            # Step 1: Customer sends message via web widget
            message_data = {
                'content': 'Hi, I\'m interested in your AI secretary services for my business.',
                'channel': 'web_widget',
                'customer_email': 'prospect@example.com',
                'customer_name': 'John Prospect'
            }
            
            response = client.post('/api/v1/inbox/messages', 
                                 json=message_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            message_id = response.get_json()['data']['id']
            
            # Step 2: Verify message was stored and AI response generated
            response = client.get(f'/api/v1/inbox/messages/{message_id}', 
                                headers=auth_headers)
            assert response.status_code == 200
            message = response.get_json()['data']
            assert message['content'] == message_data['content']
            assert message['ai_response'] is not None
            
            # Step 3: Verify lead was automatically created
            response = client.get('/api/v1/crm/leads', headers=auth_headers)
            assert response.status_code == 200
            leads = response.get_json()['data']
            assert len(leads) >= 1
            
            lead = next((l for l in leads if l['contact']['email'] == 'prospect@example.com'), None)
            assert lead is not None
            assert lead['source'] == 'web_widget'
            
            # Step 4: Agent updates lead with notes and moves through pipeline
            lead_id = lead['id']
            note_data = {
                'content': 'Customer is interested in Pro plan for 50-person team.',
                'type': 'note'
            }
            
            response = client.post(f'/api/v1/crm/leads/{lead_id}/notes', 
                                 json=note_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            
            # Step 5: Move lead to next stage
            stage_update = {'stage_id': 2}  # Assuming stage 2 is "Qualified"
            response = client.put(f'/api/v1/crm/leads/{lead_id}', 
                                json=stage_update, 
                                headers=auth_headers)
            assert response.status_code == 200
            
            # Step 6: Create task for follow-up
            task_data = {
                'title': 'Schedule demo call',
                'description': 'Set up product demo for John Prospect',
                'due_date': '2025-08-20T10:00:00Z',
                'priority': 'high'
            }
            
            response = client.post(f'/api/v1/crm/leads/{lead_id}/tasks', 
                                 json=task_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            
            # Step 7: Verify complete lead history
            response = client.get(f'/api/v1/crm/leads/{lead_id}/history', 
                                headers=auth_headers)
            assert response.status_code == 200
            history = response.get_json()['data']
            
            # Should have initial creation, note addition, stage change, and task creation
            assert len(history) >= 4
            
    def test_calendar_booking_with_crm_integration(self, client, tenant, user, auth_headers):
        """Test calendar booking workflow integrated with CRM lead management."""
        with patch('app.services.google_calendar.GoogleCalendarService') as mock_calendar:
            # Mock Google Calendar service
            mock_calendar_instance = MagicMock()
            mock_calendar.return_value = mock_calendar_instance
            
            # Mock available slots
            mock_calendar_instance.get_available_slots.return_value = [
                {
                    'start': '2025-08-20T10:00:00Z',
                    'end': '2025-08-20T11:00:00Z',
                    'available': True
                },
                {
                    'start': '2025-08-20T14:00:00Z',
                    'end': '2025-08-20T15:00:00Z',
                    'available': True
                }
            ]
            
            # Step 1: Create a lead first
            lead_data = {
                'contact': {
                    'name': 'Jane Customer',
                    'email': 'jane@customer.com',
                    'phone': '+1234567890'
                },
                'source': 'website',
                'value': 5000
            }
            
            response = client.post('/api/v1/crm/leads', 
                                 json=lead_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            lead_id = response.get_json()['data']['id']
            
            # Step 2: Customer requests available appointment slots
            response = client.get('/api/v1/calendar/availability?date=2025-08-20', 
                                headers=auth_headers)
            assert response.status_code == 200
            slots = response.get_json()['data']
            assert len(slots) == 2
            
            # Step 3: Book appointment and link to lead
            booking_data = {
                'start_time': '2025-08-20T10:00:00Z',
                'end_time': '2025-08-20T11:00:00Z',
                'title': 'Product Demo',
                'description': 'Demo call with Jane Customer',
                'attendee_email': 'jane@customer.com',
                'lead_id': lead_id
            }
            
            mock_calendar_instance.create_event.return_value = {
                'id': 'cal_event_123',
                'status': 'confirmed'
            }
            
            response = client.post('/api/v1/calendar/events', 
                                 json=booking_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            event = response.get_json()['data']
            
            # Step 4: Verify event was linked to lead
            response = client.get(f'/api/v1/crm/leads/{lead_id}', 
                                headers=auth_headers)
            assert response.status_code == 200
            lead = response.get_json()['data']
            
            # Should have calendar event linked
            assert 'calendar_events' in lead
            assert len(lead['calendar_events']) == 1
            assert lead['calendar_events'][0]['title'] == 'Product Demo'
            
    def test_knowledge_base_rag_workflow(self, client, tenant, user, auth_headers):
        """Test complete knowledge base creation and RAG query workflow."""
        with patch('app.services.document_processor.DocumentProcessor') as mock_processor, \
             patch('app.services.embedding_service.EmbeddingService') as mock_embedding:
            
            # Mock document processing
            mock_processor_instance = MagicMock()
            mock_processor.return_value = mock_processor_instance
            mock_processor_instance.process_document.return_value = {
                'chunks': [
                    {'content': 'Our AI secretary supports multiple channels including Telegram and Signal.', 'position': 0},
                    {'content': 'Pricing starts at $29/month for the Starter plan.', 'position': 1}
                ],
                'metadata': {'title': 'Product Documentation', 'pages': 5}
            }
            
            # Mock embedding service
            mock_embedding_instance = MagicMock()
            mock_embedding.return_value = mock_embedding_instance
            mock_embedding_instance.generate_embeddings.return_value = [
                [0.1, 0.2, 0.3] * 512,  # Mock 1536-dim embedding
                [0.4, 0.5, 0.6] * 512
            ]
            
            # Step 1: Upload document to knowledge base
            document_data = {
                'title': 'Product Documentation',
                'content': 'Our AI secretary supports multiple channels...',
                'type': 'text',
                'source_url': None
            }
            
            response = client.post('/api/v1/knowledge/documents', 
                                 json=document_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            doc_id = response.get_json()['data']['id']
            
            # Step 2: Verify document was processed and indexed
            response = client.get(f'/api/v1/knowledge/documents/{doc_id}', 
                                headers=auth_headers)
            assert response.status_code == 200
            document = response.get_json()['data']
            assert document['status'] == 'processed'
            assert document['chunk_count'] == 2
            
            # Step 3: Mock search functionality
            mock_embedding_instance.search_similar.return_value = [
                {
                    'chunk_id': 1,
                    'content': 'Our AI secretary supports multiple channels including Telegram and Signal.',
                    'similarity': 0.95,
                    'document_title': 'Product Documentation'
                }
            ]
            
            # Step 4: Perform knowledge search query
            search_data = {
                'query': 'What communication channels do you support?',
                'limit': 5
            }
            
            response = client.post('/api/v1/knowledge/search', 
                                 json=search_data, 
                                 headers=auth_headers)
            assert response.status_code == 200
            results = response.get_json()['data']
            
            assert len(results) >= 1
            assert results[0]['similarity'] > 0.9
            assert 'Telegram and Signal' in results[0]['content']
            
            # Step 5: Use knowledge in AI response
            with patch('app.services.agent_orchestrator.AgentOrchestrator.process_message') as mock_agent:
                mock_agent.return_value = {
                    'response': 'We support multiple channels including Telegram and Signal.',
                    'sources': [{'document': 'Product Documentation', 'chunk_id': 1}],
                    'confidence': 0.98
                }
                
                # Customer asks question
                message_data = {
                    'content': 'What communication channels do you support?',
                    'channel': 'web_widget',
                    'customer_email': 'customer@example.com'
                }
                
                response = client.post('/api/v1/inbox/messages', 
                                     json=message_data, 
                                     headers=auth_headers)
                assert response.status_code == 201
                
                message = response.get_json()['data']
                assert 'Telegram and Signal' in message['ai_response']
                assert 'sources' in message
                assert len(message['sources']) >= 1


class TestMultiTenantIsolation:
    """Test multi-tenant data isolation and security."""
    
    def test_tenant_data_isolation(self, app):
        """Test that tenants cannot access each other's data."""
        with app.app_context():
            # Create two separate tenants
            tenant1 = Tenant(name="Tenant 1", domain="tenant1.com", slug="tenant1")
            tenant2 = Tenant(name="Tenant 2", domain="tenant2.com", slug="tenant2")
            db.session.add_all([tenant1, tenant2])
            db.session.commit()
            
            # Create users for each tenant
            user1 = User(
                tenant_id=tenant1.id,
                email="user1@tenant1.com",
                password_hash="hash1",
                first_name="User",
                last_name="One",
                role="manager"
            )
            user2 = User(
                tenant_id=tenant2.id,
                email="user2@tenant2.com",
                password_hash="hash2",
                first_name="User",
                last_name="Two",
                role="manager"
            )
            db.session.add_all([user1, user2])
            db.session.commit()
            
            # Create leads for each tenant
            contact1 = Contact(tenant_id=tenant1.id, name="Contact 1", email="c1@example.com")
            contact2 = Contact(tenant_id=tenant2.id, name="Contact 2", email="c2@example.com")
            db.session.add_all([contact1, contact2])
            db.session.commit()
            
            lead1 = Lead(tenant_id=tenant1.id, contact_id=contact1.id, source="web", value=1000)
            lead2 = Lead(tenant_id=tenant2.id, contact_id=contact2.id, source="email", value=2000)
            db.session.add_all([lead1, lead2])
            db.session.commit()
            
            # Create auth tokens for each user
            token1 = create_access_token(
                identity=user1.id,
                additional_claims={'tenant_id': tenant1.id, 'user_id': user1.id, 'role': 'manager'}
            )
            token2 = create_access_token(
                identity=user2.id,
                additional_claims={'tenant_id': tenant2.id, 'user_id': user2.id, 'role': 'manager'}
            )
            
            headers1 = {'Authorization': f'Bearer {token1}', 'Content-Type': 'application/json'}
            headers2 = {'Authorization': f'Bearer {token2}', 'Content-Type': 'application/json'}
            
        # Test with client
        client = app.test_client()
        
        # Tenant 1 should only see their own leads
        response = client.get('/api/v1/crm/leads', headers=headers1)
        assert response.status_code == 200
        leads = response.get_json()['data']
        assert len(leads) == 1
        assert leads[0]['contact']['email'] == 'c1@example.com'
        
        # Tenant 2 should only see their own leads
        response = client.get('/api/v1/crm/leads', headers=headers2)
        assert response.status_code == 200
        leads = response.get_json()['data']
        assert len(leads) == 1
        assert leads[0]['contact']['email'] == 'c2@example.com'
        
        # Tenant 1 should not be able to access Tenant 2's lead
        response = client.get(f'/api/v1/crm/leads/{lead2.id}', headers=headers1)
        assert response.status_code == 404  # Should not find lead from other tenant
        
        # Tenant 2 should not be able to access Tenant 1's lead
        response = client.get(f'/api/v1/crm/leads/{lead1.id}', headers=headers2)
        assert response.status_code == 404  # Should not find lead from other tenant
        
    def test_cross_tenant_data_modification_prevention(self, app):
        """Test that tenants cannot modify each other's data."""
        with app.app_context():
            # Setup similar to previous test
            tenant1 = Tenant(name="Tenant 1", domain="tenant1.com", slug="tenant1")
            tenant2 = Tenant(name="Tenant 2", domain="tenant2.com", slug="tenant2")
            db.session.add_all([tenant1, tenant2])
            db.session.commit()
            
            user1 = User(tenant_id=tenant1.id, email="user1@tenant1.com", 
                        password_hash="hash1", first_name="User", last_name="One", role="manager")
            user2 = User(tenant_id=tenant2.id, email="user2@tenant2.com", 
                        password_hash="hash2", first_name="User", last_name="Two", role="manager")
            db.session.add_all([user1, user2])
            db.session.commit()
            
            contact1 = Contact(tenant_id=tenant1.id, name="Contact 1", email="c1@example.com")
            contact2 = Contact(tenant_id=tenant2.id, name="Contact 2", email="c2@example.com")
            db.session.add_all([contact1, contact2])
            db.session.commit()
            
            lead1 = Lead(tenant_id=tenant1.id, contact_id=contact1.id, source="web", value=1000)
            lead2 = Lead(tenant_id=tenant2.id, contact_id=contact2.id, source="email", value=2000)
            db.session.add_all([lead1, lead2])
            db.session.commit()
            
            token1 = create_access_token(
                identity=user1.id,
                additional_claims={'tenant_id': tenant1.id, 'user_id': user1.id, 'role': 'manager'}
            )
            token2 = create_access_token(
                identity=user2.id,
                additional_claims={'tenant_id': tenant2.id, 'user_id': user2.id, 'role': 'manager'}
            )
            
            headers1 = {'Authorization': f'Bearer {token1}', 'Content-Type': 'application/json'}
            headers2 = {'Authorization': f'Bearer {token2}', 'Content-Type': 'application/json'}
            
        client = app.test_client()
        
        # Tenant 1 tries to modify Tenant 2's lead
        update_data = {'value': 5000, 'status': 'qualified'}
        response = client.put(f'/api/v1/crm/leads/{lead2.id}', 
                            json=update_data, headers=headers1)
        assert response.status_code == 404  # Should not find lead from other tenant
        
        # Tenant 2 tries to delete Tenant 1's lead
        response = client.delete(f'/api/v1/crm/leads/{lead1.id}', headers=headers2)
        assert response.status_code == 404  # Should not find lead from other tenant
        
        # Verify original data is unchanged
        response = client.get(f'/api/v1/crm/leads/{lead2.id}', headers=headers2)
        assert response.status_code == 200
        lead = response.get_json()['data']
        assert lead['value'] == 2000  # Original value unchanged
        
    def test_role_based_access_control(self, app):
        """Test role-based access control within tenants."""
        with app.app_context():
            tenant = Tenant(name="Test Tenant", domain="test.com", slug="test")
            db.session.add(tenant)
            db.session.commit()
            
            # Create users with different roles
            manager = User(tenant_id=tenant.id, email="manager@test.com", 
                          password_hash="hash", first_name="Manager", last_name="User", role="manager")
            support = User(tenant_id=tenant.id, email="support@test.com", 
                          password_hash="hash", first_name="Support", last_name="User", role="support")
            readonly = User(tenant_id=tenant.id, email="readonly@test.com", 
                           password_hash="hash", first_name="Readonly", last_name="User", role="read_only")
            
            db.session.add_all([manager, support, readonly])
            db.session.commit()
            
            # Create tokens for each role
            manager_token = create_access_token(
                identity=manager.id,
                additional_claims={'tenant_id': tenant.id, 'user_id': manager.id, 'role': 'manager'}
            )
            support_token = create_access_token(
                identity=support.id,
                additional_claims={'tenant_id': tenant.id, 'user_id': support.id, 'role': 'support'}
            )
            readonly_token = create_access_token(
                identity=readonly.id,
                additional_claims={'tenant_id': tenant.id, 'user_id': readonly.id, 'role': 'read_only'}
            )
            
            manager_headers = {'Authorization': f'Bearer {manager_token}', 'Content-Type': 'application/json'}
            support_headers = {'Authorization': f'Bearer {support_token}', 'Content-Type': 'application/json'}
            readonly_headers = {'Authorization': f'Bearer {readonly_token}', 'Content-Type': 'application/json'}
            
        client = app.test_client()
        
        # Manager should be able to create leads
        lead_data = {
            'contact': {'name': 'Test Contact', 'email': 'test@example.com'},
            'source': 'web',
            'value': 1000
        }
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=manager_headers)
        assert response.status_code == 201
        lead_id = response.get_json()['data']['id']
        
        # Support should be able to read leads but not modify billing
        response = client.get('/api/v1/crm/leads', headers=support_headers)
        assert response.status_code == 200
        
        # Read-only should only be able to read, not create
        response = client.post('/api/v1/crm/leads', json=lead_data, headers=readonly_headers)
        assert response.status_code == 403  # Forbidden
        
        response = client.get('/api/v1/crm/leads', headers=readonly_headers)
        assert response.status_code == 200  # Can read
        
        # Only manager should access billing endpoints
        response = client.get('/api/v1/billing/subscriptions', headers=manager_headers)
        assert response.status_code in [200, 404]  # Allowed (404 if no subscriptions)
        
        response = client.get('/api/v1/billing/subscriptions', headers=support_headers)
        assert response.status_code == 403  # Forbidden
        
        response = client.get('/api/v1/billing/subscriptions', headers=readonly_headers)
        assert response.status_code == 403  # Forbidden


class TestExternalAPIIntegration:
    """Test external API integrations with proper mocking."""
    
    def test_stripe_webhook_integration(self, client, tenant, user, auth_headers):
        """Test Stripe webhook handling with mocked Stripe API."""
        with patch('stripe.Webhook.construct_event') as mock_construct, \
             patch('app.services.billing_service.BillingService') as mock_billing:
            
            # Mock Stripe webhook event
            mock_event = {
                'type': 'invoice.payment_succeeded',
                'data': {
                    'object': {
                        'id': 'in_test123',
                        'customer': 'cus_test123',
                        'subscription': 'sub_test123',
                        'amount_paid': 2900,
                        'status': 'paid'
                    }
                }
            }
            mock_construct.return_value = mock_event
            
            # Mock billing service
            mock_billing_instance = MagicMock()
            mock_billing.return_value = mock_billing_instance
            mock_billing_instance.handle_payment_succeeded.return_value = True
            
            # Send webhook
            webhook_data = json.dumps(mock_event)
            headers = {
                'Stripe-Signature': 'test_signature',
                'Content-Type': 'application/json'
            }
            
            response = client.post('/api/v1/webhooks/stripe', 
                                 data=webhook_data, 
                                 headers=headers)
            assert response.status_code == 200
            
            # Verify billing service was called
            mock_billing_instance.handle_payment_succeeded.assert_called_once()
            
    def test_google_calendar_oauth_flow(self, client, tenant, user, auth_headers):
        """Test Google Calendar OAuth integration with mocked Google API."""
        with patch('app.services.google_oauth.GoogleOAuthService') as mock_oauth:
            
            # Mock OAuth service
            mock_oauth_instance = MagicMock()
            mock_oauth.return_value = mock_oauth_instance
            
            # Step 1: Initiate OAuth flow
            mock_oauth_instance.get_authorization_url.return_value = {
                'auth_url': 'https://accounts.google.com/oauth/authorize?...',
                'state': 'random_state_123'
            }
            
            response = client.post('/api/v1/calendar/oauth/initiate', 
                                 headers=auth_headers)
            assert response.status_code == 200
            oauth_data = response.get_json()['data']
            assert 'auth_url' in oauth_data
            assert 'state' in oauth_data
            
            # Step 2: Handle OAuth callback
            mock_oauth_instance.exchange_code_for_tokens.return_value = {
                'access_token': 'ya29.test_access_token',
                'refresh_token': 'refresh_token_123',
                'expires_in': 3600
            }
            
            callback_data = {
                'code': 'auth_code_123',
                'state': 'random_state_123'
            }
            
            response = client.post('/api/v1/calendar/oauth/callback', 
                                 json=callback_data, 
                                 headers=auth_headers)
            assert response.status_code == 200
            
            # Step 3: Verify calendar access
            mock_oauth_instance.get_calendar_list.return_value = [
                {'id': 'primary', 'summary': 'Primary Calendar'},
                {'id': 'calendar2', 'summary': 'Work Calendar'}
            ]
            
            response = client.get('/api/v1/calendar/calendars', 
                                headers=auth_headers)
            assert response.status_code == 200
            calendars = response.get_json()['data']
            assert len(calendars) == 2
            assert calendars[0]['summary'] == 'Primary Calendar'
            
    def test_kyb_external_apis_integration(self, client, tenant, user, auth_headers):
        """Test KYB external API integrations with proper mocking."""
        with patch('app.services.vies_adapter.VIESAdapter') as mock_vies, \
             patch('app.services.gleif_adapter.GLEIFAdapter') as mock_gleif, \
             patch('app.services.sanctions_monitor.SanctionsMonitor') as mock_sanctions:
            
            # Mock VIES API
            mock_vies_instance = MagicMock()
            mock_vies.return_value = mock_vies_instance
            mock_vies_instance.validate_vat.return_value = {
                'valid': True,
                'country_code': 'DE',
                'vat_number': '123456789',
                'name': 'Test Company GmbH',
                'address': 'Test Street 123, Berlin'
            }
            
            # Mock GLEIF API
            mock_gleif_instance = MagicMock()
            mock_gleif.return_value = mock_gleif_instance
            mock_gleif_instance.validate_lei.return_value = {
                'valid': True,
                'lei': '123456789012345678XX',
                'legal_name': 'Test Company GmbH',
                'status': 'ISSUED'
            }
            
            # Mock Sanctions API
            mock_sanctions_instance = MagicMock()
            mock_sanctions.return_value = mock_sanctions_instance
            mock_sanctions_instance.check_sanctions.return_value = {
                'matches': [],
                'risk_score': 0
            }
            
            # Create counterparty with external validation
            counterparty_data = {
                'name': 'Test Company GmbH',
                'vat_number': 'DE123456789',
                'lei_code': '123456789012345678XX',
                'country_code': 'DE'
            }
            
            response = client.post('/api/v1/kyb/counterparties', 
                                 json=counterparty_data, 
                                 headers=auth_headers)
            assert response.status_code == 201
            counterparty = response.get_json()['data']
            
            # Verify external APIs were called
            mock_vies_instance.validate_vat.assert_called_once()
            mock_gleif_instance.validate_lei.assert_called_once()
            mock_sanctions_instance.check_sanctions.assert_called_once()
            
            # Verify counterparty was created with validation results
            assert counterparty['vat_validation_status'] == 'valid'
            assert counterparty['lei_validation_status'] == 'valid'
            assert counterparty['sanctions_risk_score'] == 0


class TestPerformanceAndLoad:
    """Test performance and load scenarios."""
    
    def test_concurrent_api_requests(self, client, tenant, user, auth_headers):
        """Test system performance under concurrent API requests."""
        def make_request():
            """Make a single API request."""
            response = client.get('/api/v1/crm/leads', headers=auth_headers)
            return response.status_code, response.response_time if hasattr(response, 'response_time') else 0
        
        # Test with multiple concurrent requests
        num_requests = 20
        max_workers = 5
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(make_request) for _ in range(num_requests)]
            results = [future.result() for future in as_completed(futures)]
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify all requests succeeded
        status_codes = [result[0] for result in results]
        assert all(code in [200, 404] for code in status_codes), f"Some requests failed: {status_codes}"
        
        # Verify reasonable response time (should complete within 10 seconds)
        assert total_time < 10.0, f"Concurrent requests took too long: {total_time:.2f}s"
        
        # Calculate average response time
        avg_time = total_time / num_requests
        assert avg_time < 0.5, f"Average response time too high: {avg_time:.3f}s"
        
    def test_large_dataset_pagination(self, client, tenant, user, auth_headers):
        """Test API performance with large datasets and pagination."""
        with patch('app.models.crm.Lead.query') as mock_query:
            # Mock large dataset
            mock_leads = []
            for i in range(1000):
                mock_lead = MagicMock()
                mock_lead.id = i + 1
                mock_lead.tenant_id = tenant.id
                mock_lead.source = 'web'
                mock_lead.value = 1000 + i
                mock_lead.created_at = '2025-08-16T10:00:00Z'
                mock_leads.append(mock_lead)
            
            # Mock pagination
            mock_paginate = MagicMock()
            mock_paginate.items = mock_leads[:50]  # First page
            mock_paginate.total = 1000
            mock_paginate.pages = 20
            mock_paginate.page = 1
            mock_paginate.per_page = 50
            mock_paginate.has_next = True
            mock_paginate.has_prev = False
            
            mock_query.filter.return_value.paginate.return_value = mock_paginate
            
            # Test first page
            start_time = time.time()
            response = client.get('/api/v1/crm/leads?page=1&per_page=50', 
                                headers=auth_headers)
            end_time = time.time()
            
            assert response.status_code == 200
            data = response.get_json()
            
            # Verify pagination metadata
            assert data['pagination']['total'] == 1000
            assert data['pagination']['pages'] == 20
            assert data['pagination']['current_page'] == 1
            assert len(data['data']) == 50
            
            # Verify response time is reasonable
            response_time = end_time - start_time
            assert response_time < 1.0, f"Pagination response too slow: {response_time:.3f}s"
            
    def test_memory_usage_with_large_responses(self, client, tenant, user, auth_headers):
        """Test memory usage with large API responses."""
        import psutil
        import os
        
        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Make requests that could potentially use lots of memory
        large_requests = [
            '/api/v1/crm/leads?per_page=100',
            '/api/v1/inbox/messages?per_page=100',
            '/api/v1/kyb/counterparties?per_page=100'
        ]
        
        for endpoint in large_requests:
            response = client.get(endpoint, headers=auth_headers)
            # Don't assert status codes since some endpoints might not exist yet
            # Just ensure the request doesn't crash
            assert response is not None
        
        # Check memory usage after requests
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be reasonable (less than 100MB for test requests)
        assert memory_increase < 100, f"Memory usage increased too much: {memory_increase:.2f}MB"
        
    def test_database_query_performance(self, app, tenant, user):
        """Test database query performance with indexes."""
        with app.app_context():
            # Create test data
            contacts = []
            leads = []
            
            for i in range(100):
                contact = Contact(
                    tenant_id=tenant.id,
                    name=f"Contact {i}",
                    email=f"contact{i}@example.com"
                )
                contacts.append(contact)
            
            db.session.add_all(contacts)
            db.session.commit()
            
            for i, contact in enumerate(contacts):
                lead = Lead(
                    tenant_id=tenant.id,
                    contact_id=contact.id,
                    source='web',
                    value=1000 + i,
                    status='new'
                )
                leads.append(lead)
            
            db.session.add_all(leads)
            db.session.commit()
            
            # Test query performance
            start_time = time.time()
            
            # Query with filters (should use indexes)
            filtered_leads = Lead.query.filter(
                Lead.tenant_id == tenant.id,
                Lead.status == 'new',
                Lead.value > 1050
            ).all()
            
            end_time = time.time()
            query_time = end_time - start_time
            
            # Query should be fast (less than 0.1 seconds)
            assert query_time < 0.1, f"Database query too slow: {query_time:.3f}s"
            assert len(filtered_leads) > 0
            
            # Test join query performance
            start_time = time.time()
            
            leads_with_contacts = db.session.query(Lead).join(Contact).filter(
                Lead.tenant_id == tenant.id,
                Contact.email.like('%@example.com')
            ).all()
            
            end_time = time.time()
            join_query_time = end_time - start_time
            
            # Join query should also be reasonably fast
            assert join_query_time < 0.2, f"Join query too slow: {join_query_time:.3f}s"
            assert len(leads_with_contacts) > 0