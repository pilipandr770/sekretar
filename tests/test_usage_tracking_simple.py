#!/usr/bin/env python3
"""Simple usage tracking tests for billing and subscription testing.

This test suite covers:
- Usage limit monitoring tests
- Overage calculation tests  
- Entitlement management tests

Requirements: 6.3, 6.4
"""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

def test_usage_limit_monitoring():
    """Test usage limit monitoring functionality."""
    print("Testing usage limit monitoring...")
    
    try:
        from app import create_app, db
        from app.models.billing import Plan, Subscription, Entitlement, UsageEvent
        from app.models.tenant import Tenant
        
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            # Create test data
            tenant = Tenant.create(
                name="Test Company",
                domain="test.com",
                settings={}
            )
            
            plan = Plan.create(
                name="Test Plan",
                description="Test plan for usage tracking",
                price=Decimal('29.99'),
                billing_interval='month',
                features={'ai_responses': True, 'crm': True},
                limits={
                    'messages_per_month': 1000,
                    'knowledge_documents': 50,
                    'leads': 500
                }
            )
            
            subscription = Subscription.create(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status='active',
                current_period_start=datetime.utcnow().isoformat(),
                current_period_end=(datetime.utcnow() + timedelta(days=30)).isoformat()
            )
            
            # Create entitlements
            entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, plan)
            
            # Test usage within limits
            messages_entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
            messages_entitlement.used_value = 500
            messages_entitlement.save()
            
            assert not messages_entitlement.is_over_limit
            assert messages_entitlement.usage_percentage == 50.0
            assert messages_entitlement.remaining_quota() == 500
            assert messages_entitlement.can_use(100)
            
            print(f"✓ Usage within limits: {messages_entitlement.used_value}/{messages_entitlement.limit_value}")
            print(f"✓ Usage percentage: {messages_entitlement.usage_percentage}%")
            print(f"✓ Remaining quota: {messages_entitlement.remaining_quota()}")
            
            # Test usage approaching limit (90%)
            messages_entitlement.used_value = 900
            messages_entitlement.save()
            
            assert not messages_entitlement.is_over_limit
            assert messages_entitlement.usage_percentage == 90.0
            assert messages_entitlement.remaining_quota() == 100
            assert messages_entitlement.can_use(50)
            assert not messages_entitlement.can_use(150)  # Would exceed limit
            
            print(f"✓ Usage approaching limit: {messages_entitlement.used_value}/{messages_entitlement.limit_value}")
            print(f"✓ Usage percentage: {messages_entitlement.usage_percentage}%")
            
            # Test usage over limit
            messages_entitlement.used_value = 1200
            messages_entitlement.save()
            
            assert messages_entitlement.is_over_limit
            assert messages_entitlement.usage_percentage == 120.0
            assert messages_entitlement.remaining_quota() == 0
            assert not messages_entitlement.can_use(1)
            
            print(f"✓ Usage over limit: {messages_entitlement.used_value}/{messages_entitlement.limit_value}")
            print(f"✓ Over limit detected: {messages_entitlement.is_over_limit}")
            
            # Test unlimited plan
            unlimited_plan = Plan.create(
                name="Unlimited Plan",
                description="Unlimited usage plan",
                price=Decimal('299.99'),
                billing_interval='month',
                features={'ai_responses': True, 'crm': True},
                limits={
                    'messages_per_month': -1,  # Unlimited
                    'knowledge_documents': -1,
                    'leads': -1
                }
            )
            
            unlimited_tenant = Tenant.create(name="Unlimited Company", domain="unlimited.com", settings={})
            unlimited_subscription = Subscription.create(
                tenant_id=unlimited_tenant.id,
                plan_id=unlimited_plan.id,
                status='active'
            )
            
            unlimited_entitlements = Entitlement.create_from_plan(unlimited_tenant.id, unlimited_subscription.id, unlimited_plan)
            unlimited_entitlement = Entitlement.get_by_feature(unlimited_subscription.id, 'messages_per_month')
            unlimited_entitlement.used_value = 10000  # High usage
            unlimited_entitlement.save()
            
            assert unlimited_entitlement.is_unlimited
            assert not unlimited_entitlement.is_over_limit
            assert unlimited_entitlement.usage_percentage == 0.0
            assert unlimited_entitlement.remaining_quota() == -1
            assert unlimited_entitlement.can_use(999999)
            
            print(f"✓ Unlimited plan detected: {unlimited_entitlement.is_unlimited}")
            print(f"✓ High usage allowed: {unlimited_entitlement.used_value}")
            
            db.drop_all()
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_overage_calculation():
    """Test overage calculation functionality."""
    print("Testing overage calculation...")
    
    try:
        from app import create_app
        from app.services.subscription_service import SubscriptionService
        from app.models.billing import Subscription
        
        app = create_app('testing')
        with app.app_context():
            service = SubscriptionService()
            subscription = Subscription()  # Mock subscription
            
            # Test basic overage calculation
            test_cases = [
                ('messages_per_month', 100, Decimal('1.00')),  # $0.01 per message
                ('knowledge_documents', 10, Decimal('1.00')),  # $0.10 per document
                ('leads', 50, Decimal('2.50')),  # $0.05 per lead
                ('users', 2, Decimal('10.00')),  # $5.00 per user
            ]
            
            for feature, overage_amount, expected_cost in test_cases:
                cost = service._calculate_overage_cost(subscription, feature, overage_amount)
                assert cost == expected_cost
                print(f"✓ {feature}: {overage_amount} × rate = ${cost}")
            
            # Test unknown feature (should have zero cost)
            cost = service._calculate_overage_cost(subscription, 'unknown_feature', 100)
            assert cost == Decimal('0.00')
            print(f"✓ Unknown feature overage cost: ${cost}")
            
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_entitlement_management():
    """Test entitlement management functionality."""
    print("Testing entitlement management...")
    
    try:
        from app import create_app, db
        from app.models.billing import Plan, Subscription, Entitlement
        from app.models.tenant import Tenant
        
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            # Create test plan
            plan = Plan.create(
                name="Entitlement Test Plan",
                price=Decimal('49.99'),
                features={'ai_responses': True, 'crm': True, 'calendar': True},
                limits={
                    'messages_per_month': 2000,
                    'knowledge_documents': 100,
                    'leads': 1000,
                    'users': 5
                }
            )
            
            tenant = Tenant.create(name="Entitlement Co", domain="entitlement.co", settings={})
            subscription = Subscription.create(tenant_id=tenant.id, plan_id=plan.id, status='active')
            
            # Test entitlement creation from plan
            entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, plan)
            
            assert len(entitlements) == 4  # 4 limits in plan
            
            expected_limits = {
                'messages_per_month': 2000,
                'knowledge_documents': 100,
                'leads': 1000,
                'users': 5
            }
            
            for entitlement in entitlements:
                assert entitlement.tenant_id == tenant.id
                assert entitlement.subscription_id == subscription.id
                assert entitlement.feature in expected_limits
                assert entitlement.limit_value == expected_limits[entitlement.feature]
                assert entitlement.used_value == 0
                
                # Check reset frequency
                if entitlement.feature.endswith('_per_month'):
                    assert entitlement.reset_frequency == 'monthly'
                else:
                    assert entitlement.reset_frequency == 'never'
            
            print(f"✓ Created {len(entitlements)} entitlements from plan")
            
            # Test usage increment/decrement
            test_entitlement = Entitlement.create(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                feature='test_feature',
                limit_value=1000,
                used_value=0
            )
            
            # Test increment
            test_entitlement.increment_usage(100)
            assert test_entitlement.used_value == 100
            
            test_entitlement.increment_usage(50)
            assert test_entitlement.used_value == 150
            
            print(f"✓ Usage incremented: {test_entitlement.used_value}")
            
            # Test decrement
            test_entitlement.decrement_usage(50)
            assert test_entitlement.used_value == 100
            
            # Test decrement below zero (should not go negative)
            test_entitlement.decrement_usage(200)
            assert test_entitlement.used_value == 0
            
            print(f"✓ Usage decremented safely: {test_entitlement.used_value}")
            
            # Test reset
            test_entitlement.used_value = 500
            test_entitlement.reset_usage()
            assert test_entitlement.used_value == 0
            
            print(f"✓ Usage reset: {test_entitlement.used_value}")
            
            # Test quota checks
            test_entitlement.limit_value = 1000
            test_entitlement.used_value = 750
            
            assert test_entitlement.remaining_quota() == 250
            assert test_entitlement.usage_percentage == 75.0
            assert not test_entitlement.is_over_limit
            assert test_entitlement.can_use(100)
            assert test_entitlement.can_use(250)
            assert not test_entitlement.can_use(300)
            
            print("✓ Quota checks passed")
            
            # Test get by feature
            messages_entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
            assert messages_entitlement is not None
            assert messages_entitlement.feature == 'messages_per_month'
            assert messages_entitlement.limit_value == 2000
            
            nonexistent = Entitlement.get_by_feature(subscription.id, 'nonexistent_feature')
            assert nonexistent is None
            
            print(f"✓ Found entitlement by feature: {messages_entitlement.feature}")
            print(f"✓ Non-existent feature returns None: {nonexistent is None}")
            
            db.drop_all()
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usage_quota_enforcement():
    """Test usage quota enforcement functionality."""
    print("Testing usage quota enforcement...")
    
    try:
        from app import create_app, db
        from app.services.subscription_service import SubscriptionService
        from app.models.billing import Plan, Subscription, Entitlement
        from app.models.tenant import Tenant
        
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            service = SubscriptionService()
            
            # Create tenant with usage within limits
            tenant = Tenant.create(name="Good Tenant", domain="good-tenant.com", settings={})
            plan = Plan.create(name="Good Plan", price=Decimal('49.99'), limits={'messages_per_month': 3000})
            subscription = Subscription.create(tenant_id=tenant.id, plan_id=plan.id, status='active')
            
            entitlement = Entitlement.create(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                feature='messages_per_month',
                limit_value=3000,
                used_value=2000  # Within limit
            )
            
            # Mock current usage to return usage within limits
            def mock_get_current_usage(subscription_id, feature):
                return 2000
            
            service._get_current_usage = mock_get_current_usage
            
            # Enforce quotas
            result = service.enforce_usage_quotas(tenant.id)
            
            # Verify no enforcement needed
            assert result['tenant_id'] == tenant.id
            assert result['enforced_count'] == 0
            assert len(result['results']) == 0
            
            print(f"✓ No quota enforcement needed: {result['enforced_count']} overages")
            
            # Test with overage scenario
            overage_tenant = Tenant.create(name="Overage Tenant", domain="overage-tenant.com", settings={})
            overage_plan = Plan.create(
                name="Standard Plan",
                price=Decimal('79.99'),
                limits={'messages_per_month': 5000}
            )
            overage_subscription = Subscription.create(
                tenant_id=overage_tenant.id,
                plan_id=overage_plan.id,
                status='active',
                stripe_customer_id='cus_overage123'
            )
            
            overage_entitlement = Entitlement.create(
                tenant_id=overage_tenant.id,
                subscription_id=overage_subscription.id,
                feature='messages_per_month',
                limit_value=5000,
                used_value=6000  # Over by 1000
            )
            
            # Mock current usage to return overage
            def mock_get_current_usage_overage(subscription_id, feature):
                if subscription_id == overage_subscription.id:
                    return 6000
                return 0
            
            service._get_current_usage = mock_get_current_usage_overage
            
            # Mock invoice creation to avoid Stripe calls
            with patch.object(service, '_create_overage_invoice') as mock_create_invoice:
                mock_invoice = Mock()
                mock_invoice.id = 1
                mock_create_invoice.return_value = mock_invoice
                
                # Enforce quotas
                result = service.enforce_usage_quotas(overage_tenant.id)
                
                # Verify overage was processed
                assert result['tenant_id'] == overage_tenant.id
                assert result['enforced_count'] == 1
                assert len(result['results']) == 1
                
                overage_result = result['results'][0]
                assert overage_result['subscription_id'] == overage_subscription.id
                assert overage_result['feature'] == 'messages_per_month'
                assert overage_result['current_usage'] == 6000
                assert overage_result['limit'] == 5000
                assert overage_result['overage_result']['action'] == 'overage_billed'
                assert overage_result['overage_result']['overage_amount'] == 1000
                
                print(f"✓ Quota enforcement completed: {result['enforced_count']} overages")
                print(f"✓ Messages overage: {overage_result['overage_result']['overage_amount']}")
            
            db.drop_all()
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_usage_event_recording():
    """Test usage event recording functionality."""
    print("Testing usage event recording...")
    
    try:
        from app import create_app, db
        from app.models.billing import UsageEvent, Subscription, Plan
        from app.models.tenant import Tenant
        
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            
            # Create test data
            tenant = Tenant.create(name="Usage Co", domain="usage.co", settings={})
            plan = Plan.create(name="Usage Plan", price=Decimal('29.99'), limits={'messages_per_month': 1000})
            subscription = Subscription.create(tenant_id=tenant.id, plan_id=plan.id, status='active')
            
            # Test usage event recording
            usage_event = UsageEvent.record_usage(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                event_type='messages_per_month',
                quantity=50,
                source='telegram',
                channel='telegram'
            )
            
            assert usage_event.tenant_id == tenant.id
            assert usage_event.subscription_id == subscription.id
            assert usage_event.event_type == 'messages_per_month'
            assert usage_event.quantity == 50
            assert usage_event.get_metadata('source') == 'telegram'
            assert usage_event.get_metadata('channel') == 'telegram'
            
            print(f"✓ Usage event recorded: {usage_event.event_type} x{usage_event.quantity}")
            
            # Test usage aggregation
            # Record more events
            for i in range(5):
                UsageEvent.record_usage(
                    tenant_id=tenant.id,
                    subscription_id=subscription.id,
                    event_type='messages_per_month',
                    quantity=10,
                    source='telegram'
                )
            
            # Get total usage
            total_usage = UsageEvent.get_total_usage(
                subscription_id=subscription.id,
                event_type='messages_per_month'
            )
            
            assert total_usage == 100  # 50 + (5 * 10)
            print(f"✓ Total usage calculated: {total_usage}")
            
            # Test usage for period
            from datetime import datetime, timedelta
            start_date = (datetime.utcnow() - timedelta(hours=1)).isoformat()
            end_date = datetime.utcnow().isoformat()
            
            period_events = UsageEvent.get_usage_for_period(
                subscription_id=subscription.id,
                event_type='messages_per_month',
                start_date=start_date,
                end_date=end_date
            )
            
            assert len(period_events) == 6  # All events should be within the period
            print(f"✓ Period usage events: {len(period_events)}")
            
            db.drop_all()
            return True
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all usage tracking tests."""
    print("=== Usage Tracking Tests ===\n")
    
    tests = [
        test_usage_limit_monitoring,
        test_overage_calculation,
        test_entitlement_management,
        test_usage_quota_enforcement,
        test_usage_event_recording
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
        print("✓ All usage tracking tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)