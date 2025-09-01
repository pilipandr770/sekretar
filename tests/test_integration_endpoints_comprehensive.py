"""Comprehensive integration endpoint tests for Telegram webhooks, Stripe webhooks, and knowledge search API.

This test suite covers:
- Telegram webhook processing tests
- Stripe webhook handling tests  
- Knowledge search API tests

Requirements: 2.2, 5.1, 6.1
"""
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime


class TestTelegramWebhookIntegration:
    """Test Telegram webhook processing integration."""
    
    def test_telegram_webhook_text_message_processing(self, client):
        """Test processing text message through Telegram webhook."""
        webhook_data = {
            "update_id": 123456789,
            "message": {
                "message_id": 1,
                "date": int(datetime.now().timestamp()),
                "text": "Hello, I need help with my account",
                "from": {
                    "id": 12345,
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe",
                    "language_code": "en"
                },
                "chat": {
                    "id": 12345,
                    "type": "private",
                    "first_name": "John",
                    "last_name": "Doe",
                    "username": "johndoe"
                }
            }
        }
        
        with patch('app.services.telegram_service.TelegramService.process_webhook_update') as mock_process:
            mock_process.return_value = {
                "status": "success",
                "processed": True,
                "message_id": 1,
                "chat_id": 12345
            }
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                json=webhook_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['status'] == 'success'
            assert data['data']['processed'] is True
            
            # Verify webhook processing was called
            mock_process.assert_called_once_with(webhook_data)
    
    def test_telegram_webhook_photo_message_processing(self, client):
        """Test processing photo message through Telegram webhook."""
        webhook_data = {
            "update_id": 123456790,
            "message": {
                "message_id": 2,
                "date": int(datetime.now().timestamp()),
                "caption": "Here's the document you requested",
                "photo": [
                    {
                        "file_id": "photo_123",
                        "file_unique_id": "unique_123",
                        "width": 1280,
                        "height": 720,
                        "file_size": 65536
                    }
                ],
                "from": {
                    "id": 12345,
                    "first_name": "John",
                    "username": "johndoe"
                },
                "chat": {
                    "id": 12345,
                    "type": "private"
                }
            }
        }
        
        with patch('app.services.telegram_service.TelegramService.process_webhook_update') as mock_process:
            mock_process.return_value = {
                "status": "success",
                "processed": True,
                "message_id": 2,
                "chat_id": 12345,
                "attachment_processed": True
            }
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                json=webhook_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['attachment_processed'] is True
    
    def test_telegram_webhook_callback_query_processing(self, client):
        """Test processing callback query through Telegram webhook."""
        webhook_data = {
            "update_id": 123456791,
            "callback_query": {
                "id": "callback_123",
                "data": "contact_sales",
                "from": {
                    "id": 12345,
                    "first_name": "John",
                    "username": "johndoe"
                },
                "message": {
                    "message_id": 3,
                    "date": int(datetime.now().timestamp()),
                    "text": "Quick Actions Menu",
                    "chat": {
                        "id": 12345,
                        "type": "private"
                    }
                }
            }
        }
        
        with patch('app.services.telegram_service.TelegramService.process_webhook_update') as mock_process:
            mock_process.return_value = {
                "status": "success",
                "processed": True,
                "callback_query_id": "callback_123",
                "action": "contact_sales"
            }
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                json=webhook_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['action'] == 'contact_sales'
    
    def test_telegram_webhook_invalid_data(self, client):
        """Test Telegram webhook with invalid data."""
        invalid_data = {
            "invalid": "data"
        }
        
        with patch('app.services.telegram_service.TelegramService.process_webhook_update') as mock_process:
            mock_process.return_value = {
                "error": "Could not determine chat ID from update"
            }
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                json=invalid_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'error' in data
    
    def test_telegram_webhook_no_data(self, client):
        """Test Telegram webhook with no data."""
        response = client.post(
            '/api/v1/channels/telegram/webhook',
            headers={'Content-Type': 'application/json'}
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'No update data provided' in data['error']['message']
    
    def test_telegram_webhook_ai_processing_integration(self, client):
        """Test Telegram webhook with AI agent processing."""
        webhook_data = {
            "update_id": 123456793,
            "message": {
                "message_id": 5,
                "date": int(datetime.now().timestamp()),
                "text": "I want to upgrade my subscription plan",
                "from": {
                    "id": 12345,
                    "first_name": "John",
                    "username": "johndoe"
                },
                "chat": {
                    "id": 12345,
                    "type": "private"
                }
            }
        }
        
        with patch('app.services.telegram_service.TelegramService.process_webhook_update') as mock_process:
            mock_process.return_value = {
                "status": "success",
                "processed": True,
                "message_id": 5,
                "chat_id": 12345,
                "ai_response": {
                    "content": "I'd be happy to help you upgrade your subscription. Let me check your current plan.",
                    "intent": "billing_inquiry",
                    "confidence": 0.95,
                    "agent": "billing_agent"
                }
            }
            
            response = client.post(
                '/api/v1/channels/telegram/webhook',
                json=webhook_data,
                headers={'Content-Type': 'application/json'}
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['ai_response']['intent'] == 'billing_inquiry'
            assert data['data']['ai_response']['agent'] == 'billing_agent'


class TestStripeWebhookIntegration:
    """Test Stripe webhook handling integration."""
    
    def test_stripe_webhook_invoice_payment_succeeded(self, client):
        """Test Stripe webhook for successful invoice payment."""
        webhook_data = {
            "id": "evt_test123",
            "type": "invoice.payment_succeeded",
            "data": {
                "object": {
                    "id": "in_test123",
                    "status": "paid",
                    "amount_paid": 2900,  # In cents
                    "status_transitions": {
                        "paid_at": int(datetime.utcnow().timestamp())
                    }
                }
            }
        }
        
        headers = {
            'Stripe-Signature': 'test_signature',
            'Content-Type': 'application/json'
        }
        
        with patch('flask.current_app.config.get') as mock_config:
            mock_config.return_value = 'test_webhook_secret'
            
            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = webhook_data
                with patch('app.billing.webhooks.handle_invoice_payment_succeeded') as mock_handler:
                    mock_handler.return_value = True
                    
                    response = client.post(
                        '/api/v1/billing/webhooks/stripe',
                        data=json.dumps(webhook_data),
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    assert data['data']['event_type'] == 'invoice.payment_succeeded'
                    
                    # Verify webhook construction was called
                    mock_construct.assert_called_once()
                    
                    # Verify handler was called
                    mock_handler.assert_called_once()
    
    def test_stripe_webhook_subscription_created(self, client):
        """Test Stripe webhook for subscription creation."""
        webhook_data = {
            "id": "evt_test125",
            "type": "customer.subscription.created",
            "data": {
                "object": {
                    "id": "sub_new123",
                    "customer": "cus_test123",
                    "status": "active",
                    "current_period_start": int(datetime.utcnow().timestamp()),
                    "current_period_end": int(datetime.utcnow().timestamp() + 2592000),  # +30 days
                    "items": {
                        "data": [{
                            "price": {
                                "id": "price_test123"
                            }
                        }]
                    },
                    "metadata": {
                        "tenant_id": "1"
                    }
                }
            }
        }
        
        headers = {
            'Stripe-Signature': 'test_signature',
            'Content-Type': 'application/json'
        }
        
        with patch('flask.current_app.config.get') as mock_config:
            mock_config.return_value = 'test_webhook_secret'
            
            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = webhook_data
                with patch('app.billing.webhooks.handle_subscription_created') as mock_handler:
                    mock_handler.return_value = True
                    
                    response = client.post(
                        '/api/v1/billing/webhooks/stripe',
                        data=json.dumps(webhook_data),
                        headers=headers
                    )
                    
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['success'] is True
                    
                    # Verify handler was called
                    mock_handler.assert_called_once()
    
    def test_stripe_webhook_invalid_signature(self, client):
        """Test Stripe webhook with invalid signature."""
        webhook_data = {
            "id": "evt_test128",
            "type": "invoice.payment_succeeded",
            "data": {"object": {}}
        }
        
        headers = {
            'Stripe-Signature': 'invalid_signature',
            'Content-Type': 'application/json'
        }
        
        with patch('flask.current_app.config.get') as mock_config:
            mock_config.return_value = 'test_webhook_secret'
            
            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.side_effect = Exception('Invalid signature')
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(webhook_data),
                    headers=headers
                )
                
                assert response.status_code == 400
                data = response.get_json()
                assert data['success'] is False
                assert 'signature' in data['error']['message'].lower()
    
    def test_stripe_webhook_missing_secret(self, client):
        """Test Stripe webhook with missing webhook secret."""
        webhook_data = {
            "id": "evt_test129",
            "type": "invoice.payment_succeeded",
            "data": {"object": {}}
        }
        
        headers = {
            'Stripe-Signature': 'test_signature',
            'Content-Type': 'application/json'
        }
        
        with patch('flask.current_app.config.get') as mock_config:
            mock_config.return_value = None  # No webhook secret
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_data),
                headers=headers
            )
            
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'secret not configured' in data['error']['message'].lower()
    
    def test_stripe_webhook_unhandled_event(self, client):
        """Test Stripe webhook with unhandled event type."""
        webhook_data = {
            "id": "evt_test130",
            "type": "some.unknown.event",
            "data": {"object": {}}
        }
        
        headers = {
            'Stripe-Signature': 'test_signature',
            'Content-Type': 'application/json'
        }
        
        with patch('flask.current_app.config.get') as mock_config:
            mock_config.return_value = 'test_webhook_secret'
            
            with patch('stripe.Webhook.construct_event') as mock_construct:
                mock_construct.return_value = webhook_data
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(webhook_data),
                    headers=headers
                )
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert 'ignored' in data['message'].lower()


class TestKnowledgeSearchAPIIntegration:
    """Test knowledge search API integration."""
    
    def test_knowledge_search_basic_query(self, client):
        """Test basic knowledge search functionality."""
        search_data = {
            "query": "Python programming",
            "limit": 10,
            "min_similarity": 0.1
        }
        
        with patch('flask_jwt_extended.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(tenant_id=1)
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        "document_id": 1,
                        "title": "Python Programming Guide",
                        "content_snippet": "Learn Python programming with examples",
                        "relevance_score": 0.95,
                        "source_name": "Test Knowledge Base",
                        "citations": ["Python Programming Guide"]
                    }
                ]
                
                response = client.post(
                    '/api/v1/knowledge/search',
                    json=search_data,
                    headers={'Authorization': 'Bearer fake_token'}
                )
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['query'] == 'Python programming'
                assert len(data['data']['results']) == 1
                assert data['data']['results'][0]['title'] == 'Python Programming Guide'
                assert data['data']['results'][0]['relevance_score'] == 0.95
                
                # Verify search service was called
                mock_search.assert_called_once()
    
    def test_knowledge_search_with_source_filter(self, client):
        """Test knowledge search with source ID filtering."""
        search_data = {
            "query": "JavaScript tutorial",
            "limit": 5,
            "min_similarity": 0.7,
            "source_ids": [1]
        }
        
        with patch('flask_jwt_extended.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(tenant_id=1)
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [
                    {
                        "document_id": 2,
                        "title": "JavaScript Tutorial",
                        "content_snippet": "JavaScript basics and advanced concepts",
                        "relevance_score": 0.88,
                        "source_name": "Test Knowledge Base",
                        "citations": ["JavaScript Tutorial"]
                    }
                ]
                
                response = client.post(
                    '/api/v1/knowledge/search',
                    json=search_data,
                    headers={'Authorization': 'Bearer fake_token'}
                )
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['source_ids_filter'] == [1]
                assert len(data['data']['results']) == 1
                assert data['data']['results'][0]['title'] == 'JavaScript Tutorial'
    
    def test_knowledge_search_empty_query(self, client):
        """Test knowledge search with empty query."""
        search_data = {
            "query": "   ",
            "limit": 10
        }
        
        with patch('flask_jwt_extended.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(tenant_id=1)
            
            response = client.post(
                '/api/v1/knowledge/search',
                json=search_data,
                headers={'Authorization': 'Bearer fake_token'}
            )
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'empty' in data['error']['message'].lower()
    
    def test_knowledge_search_invalid_limit(self, client):
        """Test knowledge search with invalid limit."""
        search_data = {
            "query": "test query",
            "limit": 100  # Too high
        }
        
        with patch('flask_jwt_extended.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(tenant_id=1)
            
            response = client.post(
                '/api/v1/knowledge/search',
                json=search_data,
                headers={'Authorization': 'Bearer fake_token'}
            )
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'limit' in data['error']['message'].lower()
    
    def test_knowledge_search_unauthorized(self, client):
        """Test knowledge search without authentication."""
        search_data = {
            "query": "test query"
        }
        
        response = client.post(
            '/api/v1/knowledge/search',
            json=search_data
        )
        
        assert response.status_code == 401
    
    def test_knowledge_search_service_error(self, client):
        """Test knowledge search with service error."""
        search_data = {
            "query": "test query",
            "limit": 10
        }
        
        with patch('flask_jwt_extended.get_current_user') as mock_user:
            mock_user.return_value = MagicMock(tenant_id=1)
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.side_effect = Exception("Search service error")
                
                response = client.post(
                    '/api/v1/knowledge/search',
                    json=search_data,
                    headers={'Authorization': 'Bearer fake_token'}
                )
                
                assert response.status_code == 500
                data = response.get_json()
                assert data['success'] is False
                assert 'failed to search knowledge base' in data['error']['message'].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])