"""Comprehensive Stripe integration tests for billing and subscription testing.

This test suite covers:
- Checkout session creation tests
- Webhook processing tests for payment events  
- Subscription lifecycle management tests

Requirements: 6.1, 6.2
"""
import pytest
import json
import stripe
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from flask import url_for

from app import create_app, db
from app.models.billing import Plan, Subscription, Invoice, Entitlement, UsageEvent
from app.models.tenant import Tenant
from app.models.user import User
from app.services.stripe_service import StripeService
from app.utils.exceptions import StripeError, ValidationError


@pytest.fixture
def app():
    """Create test app."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        try:
            db.drop_all()
        except Exception:
            pass  # Ignore teardown errors


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def test_tenant(app):
    """Create test tenant."""
    tenant = Tenant.create(
        name="Test Company",
        domain="test.com",
        settings={
            'stripe_customer_id': 'cus_test123',
            'billing_email': 'billing@test.com'
        }
    )
    return tenant


@pytest.fixture
def test_user(app, test_tenant):
    """Create test user."""
    user = User.create(
        email="test@test.com",
        password_hash="hashed_password",
        tenant_id=test_tenant.id,
        is_active=True,
        roles=['admin']
    )
    return user


@pytest.fixture
def test_plan(app):
    """Create test plan."""
    plan = Plan.create(
        name="Test Pro Plan",
        description="Test plan for comprehensive testing",
        price=Decimal('79.00'),
        billing_interval='month',
        features={
            'ai_responses': True,
            'crm': True,
            'calendar': True,
            'knowledge_base': True,
            'advanced_analytics': True
        },
        limits={
            'users': 10,
            'messages_per_month': 5000,
            'knowledge_documents': 200,
            'leads': 2000
        },
        stripe_price_id='price_test123',
        stripe_product_id='prod_test123',
        is_active=True,
        is_public=True
    )
    return plan


@pytest.fixture
def test_subscription(app, test_tenant, test_plan):
    """Create test subscription."""
    subscription = Subscription.create(
        tenant_id=test_tenant.id,
        plan_id=test_plan.id,
        stripe_subscription_id='sub_test123',
        stripe_customer_id='cus_test123',
        status='active',
        current_period_start=datetime.utcnow().isoformat(),
        current_period_end=(datetime.utcnow() + timedelta(days=30)).isoformat()
    )
    
    # Create entitlements
    Entitlement.create_from_plan(test_tenant.id, subscription.id, test_plan)
    
    return subscription


@pytest.fixture
def stripe_service():
    """Create StripeService instance."""
    with patch('app.services.stripe_service.stripe') as mock_stripe:
        service = StripeService()
        service.api_key = 'sk_test_123'
        yield service, mock_stripe


class TestStripeCheckoutSessions:
    """Test Stripe checkout session creation."""
    
    def test_create_checkout_session_success(self, app, stripe_service, test_tenant, test_plan):
        """Test successful checkout session creation."""
        service, mock_stripe = stripe_service
        
        # Mock Stripe checkout session
        mock_session = Mock()
        mock_session.id = 'cs_test123'
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test123'
        mock_session.payment_status = 'unpaid'
        mock_session.customer = 'cus_test123'
        mock_session.subscription = 'sub_test123'
        
        mock_stripe.checkout.Session.create.return_value = mock_session
        
        # Create checkout session
        with app.app_context():
            session_data = service.create_checkout_session(
                tenant_id=test_tenant.id,
                plan_id=test_plan.id,
                customer_email='test@test.com',
                success_url='https://test.com/success',
                cancel_url='https://test.com/cancel'
            )
        
        # Verify Stripe API call
        mock_stripe.checkout.Session.create.assert_called_once()
        call_args = mock_stripe.checkout.Session.create.call_args[1]
        
        assert call_args['mode'] == 'subscription'
        assert call_args['customer_email'] == 'test@test.com'
        assert call_args['success_url'] == 'https://test.com/success'
        assert call_args['cancel_url'] == 'https://test.com/cancel'
        assert len(call_args['line_items']) == 1
        assert call_args['line_items'][0]['price'] == test_plan.stripe_price_id
        
        # Verify response
        assert session_data['session_id'] == 'cs_test123'
        assert session_data['checkout_url'] == 'https://checkout.stripe.com/pay/cs_test123'
    
    def test_create_checkout_session_with_trial(self, app, stripe_service, test_tenant, test_plan):
        """Test checkout session creation with trial period."""
        service, mock_stripe = stripe_service
        
        mock_session = Mock()
        mock_session.id = 'cs_test123'
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test123'
        
        mock_stripe.checkout.Session.create.return_value = mock_session
        
        with app.app_context():
            session_data = service.create_checkout_session(
                tenant_id=test_tenant.id,
                plan_id=test_plan.id,
                customer_email='test@test.com',
                success_url='https://test.com/success',
                cancel_url='https://test.com/cancel',
                trial_days=7
            )
        
        # Verify trial configuration
        call_args = mock_stripe.checkout.Session.create.call_args[1]
        assert 'subscription_data' in call_args
        assert call_args['subscription_data']['trial_period_days'] == 7
    
    def test_create_checkout_session_with_existing_customer(self, app, stripe_service, test_tenant, test_plan):
        """Test checkout session creation with existing customer."""
        service, mock_stripe = stripe_service
        
        mock_session = Mock()
        mock_session.id = 'cs_test123'
        mock_session.url = 'https://checkout.stripe.com/pay/cs_test123'
        
        mock_stripe.checkout.Session.create.return_value = mock_session
        
        with app.app_context():
            session_data = service.create_checkout_session(
                tenant_id=test_tenant.id,
                plan_id=test_plan.id,
                customer_id='cus_existing123',
                success_url='https://test.com/success',
                cancel_url='https://test.com/cancel'
            )
        
        # Verify customer ID is used
        call_args = mock_stripe.checkout.Session.create.call_args[1]
        assert call_args['customer'] == 'cus_existing123'
        assert 'customer_email' not in call_args
    
    def test_create_checkout_session_stripe_error(self, app, stripe_service, test_tenant, test_plan):
        """Test checkout session creation with Stripe error."""
        service, mock_stripe = stripe_service
        
        # Mock Stripe error
        mock_stripe.checkout.Session.create.side_effect = stripe.error.StripeError("Test error")
        
        with app.app_context():
            with pytest.raises(StripeError, match="Failed to create checkout session"):
                service.create_checkout_session(
                    tenant_id=test_tenant.id,
                    plan_id=test_plan.id,
                    customer_email='test@test.com',
                    success_url='https://test.com/success',
                    cancel_url='https://test.com/cancel'
                )
    
    def test_create_checkout_session_invalid_plan(self, app, stripe_service, test_tenant):
        """Test checkout session creation with invalid plan."""
        service, mock_stripe = stripe_service
        
        with app.app_context():
            with pytest.raises(ValidationError, match="Plan not found"):
                service.create_checkout_session(
                    tenant_id=test_tenant.id,
                    plan_id=99999,  # Non-existent plan
                    customer_email='test@test.com',
                    success_url='https://test.com/success',
                    cancel_url='https://test.com/cancel'
                )


class TestStripeWebhookProcessing:
    """Test Stripe webhook processing for payment events."""
    
    def test_webhook_signature_verification(self, client, app):
        """Test webhook signature verification."""
        with app.app_context():
            # Test with invalid signature
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps({'type': 'invoice.payment_succeeded'}),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'invalid_signature'
                }
            )
            
            assert response.status_code == 400
            assert 'Invalid signature' in response.get_json()['message']
    
    @patch('app.billing.webhooks.stripe.Webhook.construct_event')
    def test_invoice_payment_succeeded_webhook(self, mock_construct_event, client, app, test_tenant, test_subscription):
        """Test invoice.payment_succeeded webhook processing."""
        # Mock webhook event
        webhook_event = {
            'id': 'evt_test123',
            'type': 'invoice.payment_succeeded',
            'data': {
                'object': {
                    'id': 'in_test123',
                    'subscription': test_subscription.stripe_subscription_id,
                    'customer': test_subscription.stripe_customer_id,
                    'status': 'paid',
                    'amount_paid': 7900,  # $79.00 in cents
                    'total': 7900,
                    'currency': 'usd',
                    'status_transitions': {
                        'paid_at': int(datetime.utcnow().timestamp())
                    }
                }
            }
        }
        
        mock_construct_event.return_value = webhook_event
        
        with app.app_context():
            # Create test invoice
            invoice = Invoice.create(
                tenant_id=test_tenant.id,
                subscription_id=test_subscription.id,
                stripe_invoice_id='in_test123',
                amount_total=Decimal('79.00'),
                amount_paid=Decimal('0.00'),
                currency='USD',
                status='open'
            )
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            
            # Verify invoice was updated
            db.session.refresh(invoice)
            assert invoice.status == 'paid'
            assert invoice.amount_paid == Decimal('79.00')
            assert invoice.paid_at is not None
    
    @patch('app.billing.webhooks.stripe.Webhook.construct_event')
    def test_invoice_payment_failed_webhook(self, mock_construct_event, client, app, test_tenant, test_subscription):
        """Test invoice.payment_failed webhook processing."""
        webhook_event = {
            'id': 'evt_test123',
            'type': 'invoice.payment_failed',
            'data': {
                'object': {
                    'id': 'in_test123',
                    'subscription': test_subscription.stripe_subscription_id,
                    'customer': test_subscription.stripe_customer_id,
                    'status': 'open',
                    'amount_paid': 0,
                    'total': 7900,
                    'currency': 'usd'
                }
            }
        }
        
        mock_construct_event.return_value = webhook_event
        
        with app.app_context():
            # Create test invoice
            invoice = Invoice.create(
                tenant_id=test_tenant.id,
                subscription_id=test_subscription.id,
                stripe_invoice_id='in_test123',
                amount_total=Decimal('79.00'),
                amount_paid=Decimal('0.00'),
                currency='USD',
                status='open'
            )
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            
            # Verify subscription status updated
            db.session.refresh(test_subscription)
            assert test_subscription.status == 'past_due'
    
    @patch('app.billing.webhooks.stripe.Webhook.construct_event')
    def test_subscription_created_webhook(self, mock_construct_event, client, app, test_tenant, test_plan):
        """Test customer.subscription.created webhook processing."""
        webhook_event = {
            'id': 'evt_test123',
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_new123',
                    'customer': 'cus_test123',
                    'status': 'active',
                    'current_period_start': int(datetime.utcnow().timestamp()),
                    'current_period_end': int((datetime.utcnow() + timedelta(days=30)).timestamp()),
                    'items': {
                        'data': [{
                            'price': {
                                'id': test_plan.stripe_price_id
                            }
                        }]
                    },
                    'metadata': {
                        'tenant_id': str(test_tenant.id),
                        'plan_id': str(test_plan.id)
                    }
                }
            }
        }
        
        mock_construct_event.return_value = webhook_event
        
        with app.app_context():
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            
            # Verify subscription was created
            subscription = Subscription.get_by_stripe_id('sub_new123')
            assert subscription is not None
            assert subscription.tenant_id == test_tenant.id
            assert subscription.plan_id == test_plan.id
            assert subscription.status == 'active'
    
    @patch('app.billing.webhooks.stripe.Webhook.construct_event')
    def test_subscription_updated_webhook(self, mock_construct_event, client, app, test_subscription):
        """Test customer.subscription.updated webhook processing."""
        webhook_event = {
            'id': 'evt_test123',
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': test_subscription.stripe_subscription_id,
                    'customer': test_subscription.stripe_customer_id,
                    'status': 'past_due',
                    'current_period_start': int(datetime.utcnow().timestamp()),
                    'current_period_end': int((datetime.utcnow() + timedelta(days=30)).timestamp()),
                    'cancel_at_period_end': True
                }
            }
        }
        
        mock_construct_event.return_value = webhook_event
        
        with app.app_context():
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            
            # Verify subscription was updated
            db.session.refresh(test_subscription)
            assert test_subscription.status == 'past_due'
            assert test_subscription.cancel_at_period_end is True
    
    @patch('app.billing.webhooks.stripe.Webhook.construct_event')
    def test_subscription_deleted_webhook(self, mock_construct_event, client, app, test_subscription):
        """Test customer.subscription.deleted webhook processing."""
        webhook_event = {
            'id': 'evt_test123',
            'type': 'customer.subscription.deleted',
            'data': {
                'object': {
                    'id': test_subscription.stripe_subscription_id,
                    'customer': test_subscription.stripe_customer_id,
                    'status': 'canceled'
                }
            }
        }
        
        mock_construct_event.return_value = webhook_event
        
        with app.app_context():
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            
            # Verify subscription was canceled
            db.session.refresh(test_subscription)
            assert test_subscription.status == 'canceled'
            assert test_subscription.canceled_at is not None
    
    @patch('app.billing.webhooks.stripe.Webhook.construct_event')
    def test_trial_will_end_webhook(self, mock_construct_event, client, app, test_subscription):
        """Test customer.subscription.trial_will_end webhook processing."""
        webhook_event = {
            'id': 'evt_test123',
            'type': 'customer.subscription.trial_will_end',
            'data': {
                'object': {
                    'id': test_subscription.stripe_subscription_id,
                    'customer': test_subscription.stripe_customer_id,
                    'status': 'trialing',
                    'trial_end': int((datetime.utcnow() + timedelta(days=3)).timestamp())
                }
            }
        }
        
        mock_construct_event.return_value = webhook_event
        
        with app.app_context():
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            # Webhook should trigger notification (tested separately)
    
    def test_unhandled_webhook_event(self, client, app):
        """Test handling of unhandled webhook events."""
        with patch('app.billing.webhooks.stripe.Webhook.construct_event') as mock_construct_event:
            webhook_event = {
                'id': 'evt_test123',
                'type': 'unknown.event.type',
                'data': {'object': {}}
            }
            
            mock_construct_event.return_value = webhook_event
            
            response = client.post(
                '/api/v1/billing/webhooks/stripe',
                data=json.dumps(webhook_event),
                headers={
                    'Content-Type': 'application/json',
                    'Stripe-Signature': 'valid_signature'
                }
            )
            
            assert response.status_code == 200
            assert 'ignored' in response.get_json()['message']


class TestSubscriptionLifecycleManagement:
    """Test subscription lifecycle management."""
    
    def test_create_subscription_success(self, app, stripe_service, test_tenant, test_plan):
        """Test successful subscription creation."""
        service, mock_stripe = stripe_service
        
        # Mock Stripe subscription
        mock_subscription = Mock()
        mock_subscription.id = 'sub_test123'
        mock_subscription.customer = 'cus_test123'
        mock_subscription.status = 'active'
        mock_subscription.current_period_start = int(datetime.utcnow().timestamp())
        mock_subscription.current_period_end = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        mock_subscription.trial_start = None
        mock_subscription.trial_end = None
        mock_subscription.items = Mock()
        mock_subscription.items.data = [Mock()]
        mock_subscription.items.data[0].id = 'si_test123'
        mock_subscription.items.data[0].price = Mock()
        mock_subscription.items.data[0].price.id = test_plan.stripe_price_id
        mock_subscription.items.data[0].quantity = 1
        
        mock_stripe.Subscription.create.return_value = mock_subscription
        
        with app.app_context():
            subscription = service.create_subscription(
                tenant_id=test_tenant.id,
                customer_id='cus_test123',
                plan_id=test_plan.id
            )
            
            # Verify Stripe API call
            mock_stripe.Subscription.create.assert_called_once()
            call_args = mock_stripe.Subscription.create.call_args[1]
            
            assert call_args['customer'] == 'cus_test123'
            assert len(call_args['items']) == 1
            assert call_args['items'][0]['price'] == test_plan.stripe_price_id
            
            # Verify local subscription
            assert subscription.tenant_id == test_tenant.id
            assert subscription.plan_id == test_plan.id
            assert subscription.stripe_subscription_id == 'sub_test123'
            assert subscription.status == 'active'
            
            # Verify entitlements were created
            entitlements = Entitlement.query.filter_by(subscription_id=subscription.id).all()
            assert len(entitlements) > 0
    
    def test_create_subscription_with_trial(self, app, stripe_service, test_tenant, test_plan):
        """Test subscription creation with trial period."""
        service, mock_stripe = stripe_service
        
        trial_start = datetime.utcnow()
        trial_end = trial_start + timedelta(days=7)
        
        mock_subscription = Mock()
        mock_subscription.id = 'sub_test123'
        mock_subscription.customer = 'cus_test123'
        mock_subscription.status = 'trialing'
        mock_subscription.current_period_start = int(trial_start.timestamp())
        mock_subscription.current_period_end = int((trial_start + timedelta(days=30)).timestamp())
        mock_subscription.trial_start = int(trial_start.timestamp())
        mock_subscription.trial_end = int(trial_end.timestamp())
        mock_subscription.items = Mock()
        mock_subscription.items.data = [Mock()]
        mock_subscription.items.data[0].id = 'si_test123'
        mock_subscription.items.data[0].price = Mock()
        mock_subscription.items.data[0].price.id = test_plan.stripe_price_id
        mock_subscription.items.data[0].quantity = 1
        
        mock_stripe.Subscription.create.return_value = mock_subscription
        
        with app.app_context():
            subscription = service.create_subscription(
                tenant_id=test_tenant.id,
                customer_id='cus_test123',
                plan_id=test_plan.id,
                trial_days=7
            )
            
            # Verify trial configuration
            call_args = mock_stripe.Subscription.create.call_args[1]
            assert call_args['trial_period_days'] == 7
            
            # Verify local subscription
            assert subscription.status == 'trialing'
            assert subscription.trial_start is not None
            assert subscription.trial_end is not None
    
    def test_update_subscription_plan(self, app, stripe_service, test_subscription, test_plan):
        """Test subscription plan update."""
        service, mock_stripe = stripe_service
        
        # Create new plan
        new_plan = Plan.create(
            name="New Plan",
            price=Decimal('99.00'),
            stripe_price_id='price_new123',
            stripe_product_id='prod_new123',
            is_active=True
        )
        
        # Mock Stripe subscription retrieval and update
        mock_current_subscription = Mock()
        mock_current_subscription.items = Mock()
        mock_current_subscription.items.data = [Mock()]
        mock_current_subscription.items.data[0].id = 'si_current123'
        
        mock_updated_subscription = Mock()
        mock_updated_subscription.id = test_subscription.stripe_subscription_id
        mock_updated_subscription.status = 'active'
        mock_updated_subscription.current_period_start = int(datetime.utcnow().timestamp())
        mock_updated_subscription.current_period_end = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        mock_updated_subscription.canceled_at = None
        
        mock_stripe.Subscription.retrieve.return_value = mock_current_subscription
        mock_stripe.Subscription.modify.return_value = mock_updated_subscription
        
        with app.app_context():
            updated_subscription = service.update_subscription(
                subscription_id=test_subscription.id,
                plan_id=new_plan.id
            )
            
            # Verify Stripe API calls
            mock_stripe.Subscription.retrieve.assert_called_once_with(test_subscription.stripe_subscription_id)
            mock_stripe.Subscription.modify.assert_called_once()
            
            modify_args = mock_stripe.Subscription.modify.call_args[1]
            assert modify_args['items'][0]['id'] == 'si_current123'
            assert modify_args['items'][0]['price'] == new_plan.stripe_price_id
            
            # Verify local subscription update
            assert updated_subscription.plan_id == new_plan.id
    
    def test_cancel_subscription_at_period_end(self, app, stripe_service, test_subscription):
        """Test subscription cancellation at period end."""
        service, mock_stripe = stripe_service
        
        mock_subscription = Mock()
        mock_subscription.id = test_subscription.stripe_subscription_id
        mock_subscription.status = 'active'
        mock_subscription.cancel_at_period_end = True
        
        mock_stripe.Subscription.modify.return_value = mock_subscription
        
        with app.app_context():
            canceled_subscription = service.cancel_subscription(
                subscription_id=test_subscription.id,
                at_period_end=True
            )
            
            # Verify Stripe API call
            mock_stripe.Subscription.modify.assert_called_once_with(
                test_subscription.stripe_subscription_id,
                cancel_at_period_end=True
            )
            
            # Verify local subscription update
            assert canceled_subscription.cancel_at_period_end is True
    
    def test_cancel_subscription_immediately(self, app, stripe_service, test_subscription):
        """Test immediate subscription cancellation."""
        service, mock_stripe = stripe_service
        
        mock_subscription = Mock()
        mock_subscription.id = test_subscription.stripe_subscription_id
        mock_subscription.status = 'canceled'
        
        mock_stripe.Subscription.delete.return_value = mock_subscription
        
        with app.app_context():
            canceled_subscription = service.cancel_subscription(
                subscription_id=test_subscription.id,
                at_period_end=False
            )
            
            # Verify Stripe API call
            mock_stripe.Subscription.delete.assert_called_once_with(test_subscription.stripe_subscription_id)
            
            # Verify local subscription update
            assert canceled_subscription.status == 'canceled'
            assert canceled_subscription.canceled_at is not None
    
    def test_reactivate_subscription(self, app, stripe_service, test_subscription):
        """Test subscription reactivation."""
        service, mock_stripe = stripe_service
        
        # Set subscription as canceled
        test_subscription.cancel_at_period_end = True
        test_subscription.save()
        
        mock_subscription = Mock()
        mock_subscription.id = test_subscription.stripe_subscription_id
        mock_subscription.status = 'active'
        mock_subscription.cancel_at_period_end = False
        
        mock_stripe.Subscription.modify.return_value = mock_subscription
        
        with app.app_context():
            reactivated_subscription = service.reactivate_subscription(test_subscription.id)
            
            # Verify Stripe API call
            mock_stripe.Subscription.modify.assert_called_once_with(
                test_subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            # Verify local subscription update
            assert reactivated_subscription.cancel_at_period_end is False
            assert reactivated_subscription.canceled_at is None
    
    def test_sync_subscription_from_stripe(self, app, stripe_service, test_tenant, test_plan):
        """Test syncing subscription data from Stripe."""
        service, mock_stripe = stripe_service
        
        # Mock Stripe subscription
        mock_subscription = Mock()
        mock_subscription.id = 'sub_sync123'
        mock_subscription.customer = 'cus_test123'
        mock_subscription.status = 'active'
        mock_subscription.current_period_start = int(datetime.utcnow().timestamp())
        mock_subscription.current_period_end = int((datetime.utcnow() + timedelta(days=30)).timestamp())
        mock_subscription.trial_start = None
        mock_subscription.trial_end = None
        mock_subscription.canceled_at = None
        mock_subscription.cancel_at_period_end = False
        mock_subscription.items = Mock()
        mock_subscription.items.data = [Mock()]
        mock_subscription.items.data[0].price = Mock()
        mock_subscription.items.data[0].price.id = test_plan.stripe_price_id
        
        mock_stripe.Subscription.retrieve.return_value = mock_subscription
        
        # Mock finding tenant by customer ID
        with patch.object(service, '_find_tenant_by_customer_id', return_value=test_tenant):
            with app.app_context():
                synced_subscription = service.sync_subscription_from_stripe('sub_sync123')
                
                # Verify Stripe API call
                mock_stripe.Subscription.retrieve.assert_called_once_with('sub_sync123')
                
                # Verify local subscription creation
                assert synced_subscription is not None
                assert synced_subscription.stripe_subscription_id == 'sub_sync123'
                assert synced_subscription.tenant_id == test_tenant.id
                assert synced_subscription.plan_id == test_plan.id
                assert synced_subscription.status == 'active'
    
    def test_subscription_error_handling(self, app, stripe_service, test_tenant, test_plan):
        """Test subscription error handling."""
        service, mock_stripe = stripe_service
        
        # Test Stripe error
        mock_stripe.Subscription.create.side_effect = stripe.error.StripeError("Test error")
        
        with app.app_context():
            with pytest.raises(StripeError, match="Failed to create subscription"):
                service.create_subscription(
                    tenant_id=test_tenant.id,
                    customer_id='cus_test123',
                    plan_id=test_plan.id
                )
        
        # Test invalid plan
        with app.app_context():
            with pytest.raises(ValidationError, match="Plan not found"):
                service.create_subscription(
                    tenant_id=test_tenant.id,
                    customer_id='cus_test123',
                    plan_id=99999  # Non-existent plan
                )


class TestUsageTracking:
    """Test usage tracking and metered billing."""
    
    def test_record_usage_success(self, app, stripe_service, test_subscription):
        """Test successful usage recording."""
        service, mock_stripe = stripe_service
        
        with app.app_context():
            success = service.record_usage(
                subscription_id=test_subscription.id,
                event_type='messages_per_month',
                quantity=10,
                metadata={'source': 'telegram', 'user_id': '123'}
            )
            
            assert success is True
            
            # Verify usage event was created
            usage_event = UsageEvent.query.filter_by(
                subscription_id=test_subscription.id,
                event_type='messages_per_month'
            ).first()
            
            assert usage_event is not None
            assert usage_event.quantity == 10
            assert usage_event.get_metadata('source') == 'telegram'
            
            # Verify entitlement was updated
            entitlement = Entitlement.get_by_feature(test_subscription.id, 'messages_per_month')
            if entitlement:
                assert entitlement.used_value >= 10
    
    def test_record_usage_over_limit(self, app, stripe_service, test_subscription):
        """Test usage recording when over limit."""
        service, mock_stripe = stripe_service
        
        with app.app_context():
            # Get entitlement and set high usage
            entitlement = Entitlement.get_by_feature(test_subscription.id, 'messages_per_month')
            if entitlement:
                entitlement.used_value = entitlement.limit_value - 5  # Near limit
                entitlement.save()
                
                # Record usage that exceeds limit
                success = service.record_usage(
                    subscription_id=test_subscription.id,
                    event_type='messages_per_month',
                    quantity=10  # This should exceed the limit
                )
                
                assert success is True
                
                # Verify entitlement is over limit
                db.session.refresh(entitlement)
                assert entitlement.is_over_limit
    
    def test_record_usage_invalid_subscription(self, app, stripe_service):
        """Test usage recording with invalid subscription."""
        service, mock_stripe = stripe_service
        
        with app.app_context():
            success = service.record_usage(
                subscription_id=99999,  # Non-existent subscription
                event_type='messages_per_month',
                quantity=10
            )
            
            assert success is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])