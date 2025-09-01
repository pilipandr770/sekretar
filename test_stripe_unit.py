#!/usr/bin/env python3
"""Unit tests for Stripe integration functionality."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
import stripe

def test_stripe_checkout_session_creation():
    """Test Stripe checkout session creation logic."""
    print("Testing Stripe checkout session creation...")
    
    try:
        # Mock the StripeService dependencies
        with patch('app.services.stripe_service.current_app') as mock_app:
            with patch('app.services.stripe_service.stripe') as mock_stripe:
                # Setup mocks
                mock_app.config.get.return_value = 'sk_test_123'
                
                # Mock plan
                mock_plan = Mock()
                mock_plan.id = 1
                mock_plan.stripe_price_id = 'price_test123'
                mock_plan.name = 'Test Plan'
                
                # Mock Stripe checkout session
                mock_session = Mock()
                mock_session.id = 'cs_test123'
                mock_session.url = 'https://checkout.stripe.com/pay/cs_test123'
                mock_session.payment_status = 'unpaid'
                mock_session.customer = 'cus_test123'
                mock_session.subscription = 'sub_test123'
                
                mock_stripe.checkout.Session.create.return_value = mock_session
                
                # Import and test the service
                from app.services.stripe_service import StripeService
                
                with patch('app.models.billing.Plan') as mock_plan_model:
                    mock_plan_model.get_by_id.return_value = mock_plan
                    
                    service = StripeService()
                    
                    # Test checkout session creation
                    result = service.create_checkout_session(
                        tenant_id=1,
                        plan_id=1,
                        customer_email='test@test.com',
                        success_url='https://test.com/success',
                        cancel_url='https://test.com/cancel'
                    )
                    
                    # Verify results
                    assert result['session_id'] == 'cs_test123'
                    assert result['checkout_url'] == 'https://checkout.stripe.com/pay/cs_test123'
                    
                    # Verify Stripe API was called correctly
                    mock_stripe.checkout.Session.create.assert_called_once()
                    call_args = mock_stripe.checkout.Session.create.call_args[1]
                    
                    assert call_args['mode'] == 'subscription'
                    assert call_args['customer_email'] == 'test@test.com'
                    assert call_args['success_url'] == 'https://test.com/success'
                    assert call_args['cancel_url'] == 'https://test.com/cancel'
                    assert len(call_args['line_items']) == 1
                    assert call_args['line_items'][0]['price'] == 'price_test123'
                    assert call_args['line_items'][0]['quantity'] == 1
                    
                    print("✓ Checkout session created successfully")
                    print(f"✓ Session ID: {result['session_id']}")
                    print(f"✓ Checkout URL: {result['checkout_url']}")
                    print("✓ Stripe API called with correct parameters")
                    
                    return True
                    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stripe_checkout_session_with_trial():
    """Test Stripe checkout session creation with trial period."""
    print("Testing Stripe checkout session with trial...")
    
    try:
        with patch('app.services.stripe_service.current_app') as mock_app:
            with patch('app.services.stripe_service.stripe') as mock_stripe:
                # Setup mocks
                mock_app.config.get.return_value = 'sk_test_123'
                
                mock_plan = Mock()
                mock_plan.id = 1
                mock_plan.stripe_price_id = 'price_test123'
                
                mock_session = Mock()
                mock_session.id = 'cs_trial123'
                mock_session.url = 'https://checkout.stripe.com/pay/cs_trial123'
                
                mock_stripe.checkout.Session.create.return_value = mock_session
                
                from app.services.stripe_service import StripeService
                
                with patch('app.models.billing.Plan') as mock_plan_model:
                    mock_plan_model.get_by_id.return_value = mock_plan
                    
                    service = StripeService()
                    
                    # Test with trial period
                    result = service.create_checkout_session(
                        tenant_id=1,
                        plan_id=1,
                        customer_email='test@test.com',
                        success_url='https://test.com/success',
                        cancel_url='https://test.com/cancel',
                        trial_days=7
                    )
                    
                    # Verify trial configuration
                    call_args = mock_stripe.checkout.Session.create.call_args[1]
                    assert 'subscription_data' in call_args
                    assert call_args['subscription_data']['trial_period_days'] == 7
                    
                    print("✓ Trial period configured correctly")
                    print(f"✓ Trial days: {call_args['subscription_data']['trial_period_days']}")
                    
                    return True
                    
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stripe_subscription_creation():
    """Test Stripe subscription creation logic."""
    print("Testing Stripe subscription creation...")
    
    try:
        with patch('app.services.stripe_service.current_app') as mock_app:
            with patch('app.services.stripe_service.stripe') as mock_stripe:
                # Setup mocks
                mock_app.config.get.return_value = 'sk_test_123'
                mock_app.logger = Mock()
                
                # Mock plan
                mock_plan = Mock()
                mock_plan.id = 1
                mock_plan.stripe_price_id = 'price_test123'
                mock_plan.name = 'Test Plan'
                
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
                mock_subscription.items.data[0].price.id = 'price_test123'
                mock_subscription.items.data[0].quantity = 1
                
                mock_stripe.Subscription.create.return_value = mock_subscription
                
                # Mock local subscription creation
                mock_local_subscription = Mock()
                mock_local_subscription.id = 1
                mock_local_subscription.tenant_id = 1
                mock_local_subscription.plan_id = 1
                mock_local_subscription.stripe_subscription_id = 'sub_test123'
                mock_local_subscription.status = 'active'
                
                from app.services.stripe_service import StripeService
                
                with patch('app.models.billing.Plan') as mock_plan_model:
                    with patch('app.models.billing.Subscription') as mock_subscription_model:
                        with patch('app.models.billing.Entitlement') as mock_entitlement_model:
                            mock_plan_model.get_by_id.return_value = mock_plan
                            mock_subscription_model.create.return_value = mock_local_subscription
                            mock_entitlement_model.create_from_plan.return_value = []
                            
                            service = StripeService()
                            
                            # Test subscription creation
                            result = service.create_subscription(
                                tenant_id=1,
                                customer_id='cus_test123',
                                plan_id=1
                            )
                            
                            # Verify Stripe API call
                            mock_stripe.Subscription.create.assert_called_once()
                            call_args = mock_stripe.Subscription.create.call_args[1]
                            
                            assert call_args['customer'] == 'cus_test123'
                            assert len(call_args['items']) == 1
                            assert call_args['items'][0]['price'] == 'price_test123'
                            
                            # Verify local subscription creation
                            mock_subscription_model.create.assert_called_once()
                            create_args = mock_subscription_model.create.call_args[1]
                            
                            assert create_args['tenant_id'] == 1
                            assert create_args['plan_id'] == 1
                            assert create_args['stripe_subscription_id'] == 'sub_test123'
                            assert create_args['status'] == 'active'
                            
                            # Verify entitlements creation
                            mock_entitlement_model.create_from_plan.assert_called_once()
                            
                            print("✓ Subscription created successfully")
                            print(f"✓ Stripe subscription ID: {mock_local_subscription.stripe_subscription_id}")
                            print(f"✓ Status: {mock_local_subscription.status}")
                            print("✓ Entitlements created")
                            
                            return True
                            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stripe_webhook_processing():
    """Test Stripe webhook processing logic."""
    print("Testing Stripe webhook processing...")
    
    try:
        # Test invoice payment succeeded webhook
        from app.billing.webhooks import handle_invoice_payment_succeeded
        
        # Mock invoice data
        invoice_data = {
            'id': 'in_test123',
            'status': 'paid',
            'amount_paid': 7900,  # $79.00 in cents
            'status_transitions': {
                'paid_at': int(datetime.utcnow().timestamp())
            }
        }
        
        # Mock invoice model
        mock_invoice = Mock()
        mock_invoice.id = 1
        mock_invoice.status = 'open'
        mock_invoice.amount_paid = Decimal('0.00')
        mock_invoice.paid_at = None
        mock_invoice.save = Mock()
        
        with patch('app.models.billing.Invoice') as mock_invoice_model:
            with patch('app.services.notification_service.NotificationService') as mock_notification:
                mock_invoice_model.get_by_stripe_id.return_value = mock_invoice
                mock_notification_service = Mock()
                mock_notification.return_value = mock_notification_service
                
                # Process webhook
                result = handle_invoice_payment_succeeded(invoice_data, {})
                
                # Verify processing
                assert result is True
                
                # Verify invoice was updated
                assert mock_invoice.status == 'paid'
                assert mock_invoice.amount_paid == Decimal('79.00')
                assert mock_invoice.paid_at is not None
                mock_invoice.save.assert_called_once()
                
                # Verify notification was sent
                mock_notification_service.send_invoice_paid_notification.assert_called_once_with(mock_invoice)
                
                print("✓ Webhook processed successfully")
                print(f"✓ Invoice status updated to: {mock_invoice.status}")
                print(f"✓ Amount paid: ${mock_invoice.amount_paid}")
                print("✓ Notification sent")
                
                return True
                
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_usage_tracking_logic():
    """Test usage tracking logic."""
    print("Testing usage tracking logic...")
    
    try:
        with patch('app.services.stripe_service.current_app') as mock_app:
            mock_app.logger = Mock()
            
            # Mock subscription
            mock_subscription = Mock()
            mock_subscription.id = 1
            mock_subscription.tenant_id = 1
            
            # Mock usage event
            mock_usage_event = Mock()
            mock_usage_event.id = 1
            mock_usage_event.event_type = 'messages_per_month'
            mock_usage_event.quantity = 50
            
            # Mock entitlement
            mock_entitlement = Mock()
            mock_entitlement.id = 1
            mock_entitlement.feature = 'messages_per_month'
            mock_entitlement.used_value = 100
            mock_entitlement.limit_value = 1000
            mock_entitlement.is_over_limit = False
            mock_entitlement.usage_percentage = 15.0
            mock_entitlement.increment_usage = Mock()
            mock_entitlement.save = Mock()
            
            from app.services.stripe_service import StripeService
            
            with patch('app.models.billing.Subscription') as mock_subscription_model:
                with patch('app.models.billing.UsageEvent') as mock_usage_event_model:
                    with patch('app.models.billing.Entitlement') as mock_entitlement_model:
                        mock_subscription_model.get_by_id.return_value = mock_subscription
                        mock_usage_event_model.record_usage.return_value = mock_usage_event
                        mock_entitlement_model.get_by_feature.return_value = mock_entitlement
                        
                        service = StripeService()
                        
                        # Test usage recording
                        result = service.record_usage(
                            subscription_id=1,
                            event_type='messages_per_month',
                            quantity=50,
                            metadata={'source': 'telegram'}
                        )
                        
                        # Verify results
                        assert result is True
                        
                        # Verify usage event was recorded
                        mock_usage_event_model.record_usage.assert_called_once()
                        record_args = mock_usage_event_model.record_usage.call_args[1]
                        
                        assert record_args['tenant_id'] == 1
                        assert record_args['subscription_id'] == 1
                        assert record_args['event_type'] == 'messages_per_month'
                        assert record_args['quantity'] == 50
                        assert record_args['source'] == 'telegram'
                        
                        # Verify entitlement was updated
                        mock_entitlement.increment_usage.assert_called_once_with(50)
                        mock_entitlement.save.assert_called_once()
                        
                        print("✓ Usage recorded successfully")
                        print(f"✓ Event type: {record_args['event_type']}")
                        print(f"✓ Quantity: {record_args['quantity']}")
                        print(f"✓ Entitlement updated: {mock_entitlement.used_value}/{mock_entitlement.limit_value}")
                        print(f"✓ Usage percentage: {mock_entitlement.usage_percentage}%")
                        
                        return True
                        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_stripe_error_handling():
    """Test Stripe error handling."""
    print("Testing Stripe error handling...")
    
    try:
        with patch('app.services.stripe_service.current_app') as mock_app:
            with patch('app.services.stripe_service.stripe') as mock_stripe:
                mock_app.config.get.return_value = 'sk_test_123'
                mock_app.logger = Mock()
                
                # Mock Stripe error
                mock_stripe.checkout.Session.create.side_effect = stripe.error.StripeError("Test error")
                
                mock_plan = Mock()
                mock_plan.id = 1
                mock_plan.stripe_price_id = 'price_test123'
                
                from app.services.stripe_service import StripeService
                from app.utils.exceptions import StripeError
                
                with patch('app.models.billing.Plan') as mock_plan_model:
                    mock_plan_model.get_by_id.return_value = mock_plan
                    
                    service = StripeService()
                    
                    # Test error handling
                    try:
                        service.create_checkout_session(
                            tenant_id=1,
                            plan_id=1,
                            customer_email='test@test.com',
                            success_url='https://test.com/success',
                            cancel_url='https://test.com/cancel'
                        )
                        print("✗ Expected StripeError was not raised")
                        return False
                    except StripeError as e:
                        assert "Failed to create checkout session" in str(e)
                        print("✓ StripeError handled correctly")
                        print(f"✓ Error message: {str(e)}")
                        return True
                        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all Stripe unit tests."""
    print("=== Stripe Integration Unit Tests ===\n")
    
    tests = [
        test_stripe_checkout_session_creation,
        test_stripe_checkout_session_with_trial,
        test_stripe_subscription_creation,
        test_stripe_webhook_processing,
        test_usage_tracking_logic,
        test_stripe_error_handling
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
        print("✓ All Stripe integration unit tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)