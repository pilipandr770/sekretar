"""Tests for Stripe webhook handling."""
import pytest
import json
from unittest.mock import patch, MagicMock
from datetime import datetime
from app.models.billing import Subscription, Invoice, Plan
from app.models.tenant import Tenant
from app.models.user import User


class TestStripeWebhooks:
    """Test Stripe webhook handling."""
    
    @pytest.fixture
    def tenant(self, db_session):
        """Create test tenant."""
        tenant = Tenant.create(
            name='Test Company',
            domain='test.com'
        )
        return tenant
    
    @pytest.fixture
    def plan(self, db_session):
        """Create test plan."""
        plan = Plan.create(
            name='Test Plan',
            price=29.00,
            stripe_price_id='price_test123',
            stripe_product_id='prod_test123'
        )
        return plan
    
    @pytest.fixture
    def subscription(self, db_session, tenant, plan):
        """Create test subscription."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            stripe_subscription_id='sub_test123',
            stripe_customer_id='cus_test123',
            status='active'
        )
        return subscription
    
    @pytest.fixture
    def invoice(self, db_session, tenant, subscription):
        """Create test invoice."""
        invoice = Invoice.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            stripe_invoice_id='in_test123',
            amount_total=29.00,
            currency='USD',
            status='open'
        )
        return invoice
    
    @pytest.fixture
    def webhook_headers(self):
        """Create webhook headers."""
        return {
            'Stripe-Signature': 'test_signature',
            'Content-Type': 'application/json'
        }
    
    def test_webhook_signature_verification_success(self, client, webhook_headers):
        """Test successful webhook signature verification."""
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_test123',
                    'status': 'paid',
                    'amount_paid': 2900,
                    'status_transitions': {
                        'paid_at': int(datetime.utcnow().timestamp())
                    }
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.billing.webhooks.handle_invoice_payment_succeeded') as mock_handler:
                mock_handler.return_value = True
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['event_type'] == 'invoice.payment_succeeded'
                mock_construct.assert_called_once()
                mock_handler.assert_called_once()
    
    def test_webhook_signature_verification_failure(self, client, webhook_headers):
        """Test webhook signature verification failure."""
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {'object': {}}
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.side_effect = Exception('Invalid signature')
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(event_data),
                headers=webhook_headers
            )
            
            assert response.status_code == 400
            data = response.get_json()
            assert data['success'] is False
            assert 'signature' in data['error']['message'].lower()
    
    def test_webhook_missing_secret(self, client, webhook_headers):
        """Test webhook with missing secret configuration."""
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {'object': {}}
        }
        
        with patch('flask.current_app.config.get') as mock_config:
            mock_config.return_value = None  # No webhook secret
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(event_data),
                headers=webhook_headers
            )
            
            assert response.status_code == 500
            data = response.get_json()
            assert data['success'] is False
            assert 'secret not configured' in data['error']['message'].lower()
    
    def test_handle_invoice_payment_succeeded(self, client, invoice, webhook_headers):
        """Test handling invoice payment succeeded event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': invoice.stripe_invoice_id,
                    'status': 'paid',
                    'amount_paid': 2900,
                    'status_transitions': {
                        'paid_at': int(datetime.utcnow().timestamp())
                    }
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.notification_service.NotificationService.send_invoice_paid_notification') as mock_notify:
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                
                # Check invoice was updated
                invoice.refresh()
                assert invoice.status == 'paid'
                assert invoice.amount_paid == 29.00
                assert invoice.paid_at is not None
                
                # Check notification was sent
                mock_notify.assert_called_once_with(invoice)
    
    def test_handle_invoice_payment_failed(self, client, invoice, webhook_headers):
        """Test handling invoice payment failed event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_failed',
            'data': {
                'object': {
                    'id': invoice.stripe_invoice_id,
                    'status': 'past_due'
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.notification_service.NotificationService.send_invoice_payment_failed_notification') as mock_notify:
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                
                # Check invoice was updated
                invoice.refresh()
                assert invoice.status == 'past_due'
                
                # Check subscription was updated
                subscription = invoice.subscription
                subscription.refresh()
                assert subscription.status == 'past_due'
                
                # Check notification was sent
                mock_notify.assert_called_once_with(invoice)
    
    def test_handle_subscription_created(self, client, tenant, plan, webhook_headers):
        """Test handling subscription created event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_new123',
                    'customer': 'cus_test123',
                    'status': 'active',
                    'current_period_start': int(datetime.utcnow().timestamp()),
                    'current_period_end': int((datetime.utcnow().timestamp()) + 2592000),  # +30 days
                    'items': {
                        'data': [{
                            'price': {
                                'id': plan.stripe_price_id
                            }
                        }]
                    },
                    'metadata': {
                        'tenant_id': str(tenant.id)
                    }
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.notification_service.NotificationService.send_subscription_created_notification') as mock_notify:
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                
                # Check subscription was created
                subscription = Subscription.get_by_stripe_id('sub_new123')
                assert subscription is not None
                assert subscription.tenant_id == tenant.id
                assert subscription.plan_id == plan.id
                assert subscription.status == 'active'
                
                # Check notification was sent
                mock_notify.assert_called_once_with(subscription)
    
    def test_handle_subscription_updated(self, client, subscription, webhook_headers):
        """Test handling subscription updated event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': subscription.stripe_subscription_id,
                    'status': 'past_due',
                    'current_period_start': int(datetime.utcnow().timestamp()),
                    'current_period_end': int((datetime.utcnow().timestamp()) + 2592000),
                    'cancel_at_period_end': True
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.notification_service.NotificationService.send_subscription_payment_failed_notification') as mock_notify:
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                
                # Check subscription was updated
                subscription.refresh()
                assert subscription.status == 'past_due'
                assert subscription.cancel_at_period_end is True
                
                # Check notification was sent
                mock_notify.assert_called_once_with(subscription)
    
    def test_handle_subscription_deleted(self, client, subscription, webhook_headers):
        """Test handling subscription deleted event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'id': subscription.stripe_subscription_id,
                    'status': 'canceled'
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.notification_service.NotificationService.send_subscription_canceled_notification') as mock_notify:
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                
                # Check subscription was updated
                subscription.refresh()
                assert subscription.status == 'canceled'
                assert subscription.canceled_at is not None
                
                # Check notification was sent
                mock_notify.assert_called_once_with(subscription)
    
    def test_handle_trial_will_end(self, client, subscription, webhook_headers):
        """Test handling subscription trial will end event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'customer.subscription.trial_will_end',
            'data': {
                'object': {
                    'id': subscription.stripe_subscription_id,
                    'status': 'trialing'
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.notification_service.NotificationService.send_trial_ending_notification') as mock_notify:
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                
                # Check notification was sent
                mock_notify.assert_called_once_with(subscription)
    
    def test_handle_unhandled_event(self, client, webhook_headers):
        """Test handling unhandled webhook event."""
        event_data = {
            'id': 'evt_test123',
            'type': 'some.unknown.event',
            'data': {'object': {}}
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(event_data),
                headers=webhook_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert 'ignored' in data['message'].lower()
    
    def test_webhook_processing_error(self, client, webhook_headers):
        """Test webhook processing error handling."""
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_nonexistent',
                    'status': 'paid'
                }
            }
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.billing.webhooks.handle_invoice_payment_succeeded') as mock_handler:
                mock_handler.return_value = False  # Simulate processing failure
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 500
                data = response.get_json()
                assert data['success'] is False
                assert 'processing' in data['error']['message'].lower()
    
    def test_invoice_sync_from_stripe(self, client, tenant, webhook_headers):
        """Test syncing invoice from Stripe when not found locally."""
        stripe_invoice_data = {
            'id': 'in_new123',
            'status': 'paid',
            'total': 2900,
            'amount_paid': 2900,
            'currency': 'usd',
            'created': int(datetime.utcnow().timestamp()),
            'number': 'INV-001',
            'hosted_invoice_url': 'https://invoice.stripe.com/test',
            'invoice_pdf': 'https://invoice.stripe.com/test.pdf',
            'status_transitions': {
                'paid_at': int(datetime.utcnow().timestamp())
            }
        }
        
        event_data = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {'object': stripe_invoice_data}
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.stripe_service.StripeService.sync_invoice_from_stripe') as mock_sync:
                mock_invoice = Invoice(
                    id=1,
                    tenant_id=tenant.id,
                    stripe_invoice_id='in_new123',
                    amount_total=29.00,
                    status='paid'
                )
                mock_sync.return_value = mock_invoice
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                mock_sync.assert_called_once_with('in_new123')
    
    def test_subscription_sync_from_stripe(self, client, tenant, plan, webhook_headers):
        """Test syncing subscription from Stripe when not found locally."""
        stripe_subscription_data = {
            'id': 'sub_new123',
            'customer': 'cus_test123',
            'status': 'active',
            'current_period_start': int(datetime.utcnow().timestamp()),
            'current_period_end': int((datetime.utcnow().timestamp()) + 2592000),
            'items': {
                'data': [{
                    'price': {'id': plan.stripe_price_id}
                }]
            },
            'metadata': {'tenant_id': str(tenant.id)}
        }
        
        event_data = {
            'id': 'evt_test123',
            'type': 'customer.subscription.updated',
            'data': {'object': stripe_subscription_data}
        }
        
        with patch('stripe.Webhook.construct_event') as mock_construct:
            mock_construct.return_value = event_data
            with patch('app.services.stripe_service.StripeService.sync_subscription_from_stripe') as mock_sync:
                mock_subscription = Subscription(
                    id=1,
                    tenant_id=tenant.id,
                    plan_id=plan.id,
                    stripe_subscription_id='sub_new123',
                    status='active'
                )
                mock_sync.return_value = mock_subscription
                
                response = client.post(
                    '/api/v1/billing/webhooks/stripe',
                    data=json.dumps(event_data),
                    headers=webhook_headers
                )
                
                assert response.status_code == 200
                mock_sync.assert_called_once_with('sub_new123')