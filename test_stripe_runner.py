#!/usr/bin/env python3
"""Simple test runner for Stripe integration tests."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from app import create_app, db
from app.models.billing import Plan, Subscription, Invoice, Entitlement
from app.models.tenant import Tenant
from app.models.user import User
from app.services.stripe_service import StripeService
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

def test_stripe_checkout_session():
    """Test Stripe checkout session creation."""
    print("Testing Stripe checkout session creation...")
    
    app = create_app('testing')
    with app.app_context():
        try:
            # Create test data
            tenant = Tenant.create(
                name="Test Company",
                domain="test.com",
                settings={'stripe_customer_id': 'cus_test123'}
            )
            
            plan = Plan.create(
                name="Test Plan",
                price=Decimal('79.00'),
                stripe_price_id='price_test123',
                stripe_product_id='prod_test123',
                is_active=True
            )
            
            # Mock Stripe service
            with patch('app.services.stripe_service.stripe') as mock_stripe:
                mock_session = Mock()
                mock_session.id = 'cs_test123'
                mock_session.url = 'https://checkout.stripe.com/pay/cs_test123'
                mock_session.payment_status = 'unpaid'
                mock_session.customer = 'cus_test123'
                mock_session.subscription = 'sub_test123'
                
                mock_stripe.checkout.Session.create.return_value = mock_session
                
                service = StripeService()
                service.api_key = 'sk_test_123'
                
                # Test checkout session creation
                session_data = service.create_checkout_session(
                    tenant_id=tenant.id,
                    plan_id=plan.id,
                    customer_email='test@test.com',
                    success_url='https://test.com/success',
                    cancel_url='https://test.com/cancel'
                )
                
                print(f"✓ Checkout session created: {session_data['session_id']}")
                print(f"✓ Checkout URL: {session_data['checkout_url']}")
                
                # Verify Stripe API was called correctly
                mock_stripe.checkout.Session.create.assert_called_once()
                call_args = mock_stripe.checkout.Session.create.call_args[1]
                
                assert call_args['mode'] == 'subscription'
                assert call_args['customer_email'] == 'test@test.com'
                assert len(call_args['line_items']) == 1
                assert call_args['line_items'][0]['price'] == plan.stripe_price_id
                
                print("✓ Stripe API called with correct parameters")
                
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    return True

def test_stripe_subscription_creation():
    """Test Stripe subscription creation."""
    print("Testing Stripe subscription creation...")
    
    app = create_app('testing')
    with app.app_context():
        try:
            # Create test data
            tenant = Tenant.create(
                name="Test Company",
                domain="test.com"
            )
            
            plan = Plan.create(
                name="Test Plan",
                price=Decimal('79.00'),
                stripe_price_id='price_test123',
                stripe_product_id='prod_test123',
                features={'ai_responses': True, 'crm': True},
                limits={'messages_per_month': 5000, 'users': 10},
                is_active=True
            )
            
            # Mock Stripe service
            with patch('app.services.stripe_service.stripe') as mock_stripe:
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
                mock_subscription.items.data[0].price.id = plan.stripe_price_id
                mock_subscription.items.data[0].quantity = 1
                
                mock_stripe.Subscription.create.return_value = mock_subscription
                
                service = StripeService()
                service.api_key = 'sk_test_123'
                
                # Test subscription creation
                subscription = service.create_subscription(
                    tenant_id=tenant.id,
                    customer_id='cus_test123',
                    plan_id=plan.id
                )
                
                print(f"✓ Subscription created: {subscription.stripe_subscription_id}")
                print(f"✓ Status: {subscription.status}")
                print(f"✓ Plan: {subscription.plan.name}")
                
                # Verify entitlements were created
                entitlements = Entitlement.query.filter_by(subscription_id=subscription.id).all()
                print(f"✓ Entitlements created: {len(entitlements)}")
                
                for entitlement in entitlements:
                    print(f"  - {entitlement.feature}: {entitlement.used_value}/{entitlement.limit_value}")
                
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    return True

def test_stripe_webhook_processing():
    """Test Stripe webhook processing."""
    print("Testing Stripe webhook processing...")
    
    app = create_app('testing')
    with app.app_context():
        try:
            # Create test data
            tenant = Tenant.create(
                name="Test Company",
                domain="test.com"
            )
            
            plan = Plan.create(
                name="Test Plan",
                price=Decimal('79.00'),
                stripe_price_id='price_test123',
                is_active=True
            )
            
            subscription = Subscription.create(
                tenant_id=tenant.id,
                plan_id=plan.id,
                stripe_subscription_id='sub_test123',
                stripe_customer_id='cus_test123',
                status='active'
            )
            
            invoice = Invoice.create(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                stripe_invoice_id='in_test123',
                amount_total=Decimal('79.00'),
                amount_paid=Decimal('0.00'),
                currency='USD',
                status='open'
            )
            
            # Test webhook processing logic
            from app.billing.webhooks import handle_invoice_payment_succeeded
            
            invoice_data = {
                'id': 'in_test123',
                'status': 'paid',
                'amount_paid': 7900,  # $79.00 in cents
                'status_transitions': {
                    'paid_at': int(datetime.utcnow().timestamp())
                }
            }
            
            # Process webhook
            success = handle_invoice_payment_succeeded(invoice_data, {})
            
            if success:
                print("✓ Webhook processed successfully")
                
                # Verify invoice was updated
                db.session.refresh(invoice)
                print(f"✓ Invoice status updated: {invoice.status}")
                print(f"✓ Amount paid: ${invoice.amount_paid}")
                
                if invoice.status == 'paid' and invoice.amount_paid == Decimal('79.00'):
                    print("✓ Invoice payment processing verified")
                else:
                    print("✗ Invoice payment processing failed")
                    return False
            else:
                print("✗ Webhook processing failed")
                return False
                
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    return True

def test_usage_tracking():
    """Test usage tracking functionality."""
    print("Testing usage tracking...")
    
    app = create_app('testing')
    with app.app_context():
        try:
            # Create test data
            tenant = Tenant.create(
                name="Test Company",
                domain="test.com"
            )
            
            plan = Plan.create(
                name="Test Plan",
                price=Decimal('79.00'),
                limits={'messages_per_month': 1000},
                is_active=True
            )
            
            subscription = Subscription.create(
                tenant_id=tenant.id,
                plan_id=plan.id,
                stripe_subscription_id='sub_test123',
                status='active'
            )
            
            # Create entitlements
            entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, plan)
            
            # Test usage recording
            service = StripeService()
            success = service.record_usage(
                subscription_id=subscription.id,
                event_type='messages_per_month',
                quantity=50,
                metadata={'source': 'telegram'}
            )
            
            if success:
                print("✓ Usage recorded successfully")
                
                # Verify usage event
                from app.models.billing import UsageEvent
                usage_event = UsageEvent.query.filter_by(
                    subscription_id=subscription.id,
                    event_type='messages_per_month'
                ).first()
                
                if usage_event:
                    print(f"✓ Usage event created: {usage_event.quantity} {usage_event.event_type}")
                    print(f"✓ Metadata: {usage_event.event_metadata}")
                else:
                    print("✗ Usage event not found")
                    return False
                
                # Verify entitlement update
                entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
                if entitlement:
                    print(f"✓ Entitlement updated: {entitlement.used_value}/{entitlement.limit_value}")
                    print(f"✓ Usage percentage: {entitlement.usage_percentage:.1f}%")
                    print(f"✓ Remaining quota: {entitlement.remaining_quota()}")
                else:
                    print("✗ Entitlement not found")
                    return False
            else:
                print("✗ Usage recording failed")
                return False
                
        except Exception as e:
            print(f"✗ Test failed: {e}")
            return False
    
    return True

def main():
    """Run all Stripe integration tests."""
    print("=== Stripe Integration Tests ===\n")
    
    tests = [
        test_stripe_checkout_session,
        test_stripe_subscription_creation,
        test_stripe_webhook_processing,
        test_usage_tracking
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        print(f"\n--- {test.__name__} ---")
        if test():
            passed += 1
            print("PASSED\n")
        else:
            print("FAILED\n")
    
    print(f"=== Results: {passed}/{total} tests passed ===")
    
    if passed == total:
        print("✓ All Stripe integration tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)