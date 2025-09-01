"""Comprehensive usage tracking tests for billing and subscription testing.

This test suite covers:
- Usage limit monitoring tests
- Overage calculation tests
- Entitlement management tests

Requirements: 6.3, 6.4
"""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app, db
from app.models.billing import Plan, Subscription, UsageEvent, Entitlement, Invoice
from app.models.tenant import Tenant
from app.models.user import User
from app.services.subscription_service import SubscriptionService
from app.services.stripe_service import StripeService
from app.utils.exceptions import ValidationError, StripeError


class TestUsageLimitMonitoring:
    """Test usage limit monitoring functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def subscription_service(self, app):
        """Create subscription service."""
        return SubscriptionService()
    
    @pytest.fixture
    def test_data(self, app):
        """Create test data."""
        # Create tenant
        tenant = Tenant.create(
            name="Test Company",
            domain="test.com",
            settings={}
        )
        
        # Create plan
        plan = Plan.create(
            name="Test Plan",
            description="Test plan for usage tracking",
            price=Decimal('29.99'),
            billing_interval='month',
            features={'ai_responses': True, 'crm': True},
            limits={
                'messages_per_month': 1000,
                'knowledge_documents': 50,
                'leads': 500,
                'users': 3
            }
        )
        
        # Create subscription
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status='active',
            current_period_start=datetime.utcnow().isoformat(),
            current_period_end=(datetime.utcnow() + timedelta(days=30)).isoformat()
        )
        
        # Create entitlements
        entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, plan)
        
        return {
            'tenant': tenant,
            'plan': plan,
            'subscription': subscription,
            'entitlements': entitlements
        }
    
    def test_usage_limit_monitoring_within_limits(self, app, subscription_service, test_data):
        """Test usage monitoring when within limits."""
        subscription = test_data['subscription']
        
        # Record usage within limits
        UsageEvent.record_usage(
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            event_type='messages_per_month',
            quantity=500,
            source='telegram'
        )
        
        # Get entitlement
        entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
        entitlement.used_value = 500
        entitlement.save()
        
        # Check usage status
        assert not entitlement.is_over_limit
        assert entitlement.usage_percentage == 50.0
        assert entitlement.remaining_quota() == 500
        assert entitlement.can_use(100)
        
        print(f"✓ Usage within limits: {entitlement.used_value}/{entitlement.limit_value}")
        print(f"✓ Usage percentage: {entitlement.usage_percentage}%")
        print(f"✓ Remaining quota: {entitlement.remaining_quota()}")
    
    def test_usage_limit_monitoring_approaching_limit(self, app, subscription_service, test_data):
        """Test usage monitoring when approaching limit."""
        subscription = test_data['subscription']
        
        # Record usage approaching limit (90%)
        UsageEvent.record_usage(
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            event_type='messages_per_month',
            quantity=900,
            source='telegram'
        )
        
        # Get entitlement
        entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
        entitlement.used_value = 900
        entitlement.save()
        
        # Check usage status
        assert not entitlement.is_over_limit
        assert entitlement.usage_percentage == 90.0
        assert entitlement.remaining_quota() == 100
        assert entitlement.can_use(50)
        assert not entitlement.can_use(150)  # Would exceed limit
        
        print(f"✓ Usage approaching limit: {entitlement.used_value}/{entitlement.limit_value}")
        print(f"✓ Usage percentage: {entitlement.usage_percentage}%")
        print(f"✓ Can use 50 more: {entitlement.can_use(50)}")
        print(f"✓ Cannot use 150 more: {not entitlement.can_use(150)}")
    
    def test_usage_limit_monitoring_over_limit(self, app, subscription_service, test_data):
        """Test usage monitoring when over limit."""
        subscription = test_data['subscription']
        
        # Record usage over limit
        UsageEvent.record_usage(
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            event_type='messages_per_month',
            quantity=1200,
            source='telegram'
        )
        
        # Get entitlement
        entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
        entitlement.used_value = 1200
        entitlement.save()
        
        # Check usage status
        assert entitlement.is_over_limit
        assert entitlement.usage_percentage == 120.0
        assert entitlement.remaining_quota() == 0
        assert not entitlement.can_use(1)
        
        print(f"✓ Usage over limit: {entitlement.used_value}/{entitlement.limit_value}")
        print(f"✓ Usage percentage: {entitlement.usage_percentage}%")
        print(f"✓ Over limit detected: {entitlement.is_over_limit}")
    
    def test_usage_limit_monitoring_unlimited_plan(self, app, subscription_service):
        """Test usage monitoring for unlimited plan."""
        # Create unlimited plan
        unlimited_plan = Plan.create(
            name="Unlimited Plan",
            description="Unlimited usage plan",
            price=Decimal('299.99'),
            billing_interval='month',
            features={'ai_responses': True, 'crm': True},
            limits={
                'messages_per_month': -1,  # Unlimited
                'knowledge_documents': -1,
                'leads': -1,
                'users': -1
            }
        )
        
        # Create tenant and subscription
        tenant = Tenant.create(name="Unlimited Company", domain="unlimited.com", settings={})
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=unlimited_plan.id,
            status='active'
        )
        
        # Create entitlements
        entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, unlimited_plan)
        
        # Get entitlement
        entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
        entitlement.used_value = 10000  # High usage
        entitlement.save()
        
        # Check unlimited status
        assert entitlement.is_unlimited
        assert not entitlement.is_over_limit
        assert entitlement.usage_percentage == 0.0
        assert entitlement.remaining_quota() == -1
        assert entitlement.can_use(999999)
        
        print(f"✓ Unlimited plan detected: {entitlement.is_unlimited}")
        print(f"✓ High usage allowed: {entitlement.used_value}")
        print(f"✓ Never over limit: {not entitlement.is_over_limit}")
    
    def test_usage_limit_monitoring_multiple_features(self, app, subscription_service, test_data):
        """Test usage monitoring across multiple features."""
        subscription = test_data['subscription']
        
        # Record usage for different features
        features_usage = {
            'messages_per_month': 800,
            'knowledge_documents': 45,
            'leads': 300,
            'users': 2
        }
        
        for feature, usage in features_usage.items():
            UsageEvent.record_usage(
                tenant_id=subscription.tenant_id,
                subscription_id=subscription.id,
                event_type=feature,
                quantity=usage,
                source='system'
            )
            
            entitlement = Entitlement.get_by_feature(subscription.id, feature)
            entitlement.used_value = usage
            entitlement.save()
        
        # Check all entitlements
        results = {}
        for feature in features_usage.keys():
            entitlement = Entitlement.get_by_feature(subscription.id, feature)
            results[feature] = {
                'used': entitlement.used_value,
                'limit': entitlement.limit_value,
                'percentage': entitlement.usage_percentage,
                'over_limit': entitlement.is_over_limit,
                'remaining': entitlement.remaining_quota()
            }
        
        # Verify results
        assert results['messages_per_month']['percentage'] == 80.0
        assert results['knowledge_documents']['percentage'] == 90.0
        assert results['leads']['percentage'] == 60.0
        assert results['users']['percentage'] == 66.67  # 2/3 * 100
        
        # None should be over limit
        for feature, data in results.items():
            assert not data['over_limit'], f"{feature} should not be over limit"
        
        print("✓ Multiple feature usage monitoring:")
        for feature, data in results.items():
            print(f"  - {feature}: {data['used']}/{data['limit']} ({data['percentage']:.1f}%)")


class TestOverageCalculation:
    """Test overage calculation functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def subscription_service(self, app):
        """Create subscription service."""
        return SubscriptionService()
    
    @pytest.fixture
    def test_subscription(self, app):
        """Create test subscription with overage."""
        tenant = Tenant.create(name="Overage Company", domain="overage.com", settings={})
        plan = Plan.create(
            name="Basic Plan",
            price=Decimal('29.99'),
            limits={'messages_per_month': 1000}
        )
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status='active',
            stripe_customer_id='cus_test123'
        )
        
        # Create entitlement
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=1200  # Over limit
        )
        
        return {
            'tenant': tenant,
            'plan': plan,
            'subscription': subscription,
            'entitlement': entitlement
        }
    
    def test_overage_calculation_basic(self, app, subscription_service, test_subscription):
        """Test basic overage calculation."""
        subscription = test_subscription['subscription']
        
        # Calculate overage cost
        overage_cost = subscription_service._calculate_overage_cost(
            subscription, 'messages_per_month', 200
        )
        
        # Verify calculation (200 * $0.01 = $2.00)
        expected_cost = Decimal('2.00')
        assert overage_cost == expected_cost
        
        print(f"✓ Overage calculation: 200 messages × $0.01 = ${overage_cost}")
    
    def test_overage_calculation_different_features(self, app, subscription_service, test_subscription):
        """Test overage calculation for different features."""
        subscription = test_subscription['subscription']
        
        test_cases = [
            ('messages_per_month', 100, Decimal('1.00')),  # $0.01 per message
            ('knowledge_documents', 10, Decimal('1.00')),  # $0.10 per document
            ('leads', 50, Decimal('2.50')),  # $0.05 per lead
            ('users', 2, Decimal('10.00')),  # $5.00 per user
        ]
        
        for feature, overage_amount, expected_cost in test_cases:
            cost = subscription_service._calculate_overage_cost(
                subscription, feature, overage_amount
            )
            assert cost == expected_cost
            print(f"✓ {feature}: {overage_amount} × rate = ${cost}")
    
    def test_overage_calculation_unknown_feature(self, app, subscription_service, test_subscription):
        """Test overage calculation for unknown feature."""
        subscription = test_subscription['subscription']
        
        # Unknown feature should have zero cost
        cost = subscription_service._calculate_overage_cost(
            subscription, 'unknown_feature', 100
        )
        
        assert cost == Decimal('0.00')
        print(f"✓ Unknown feature overage cost: ${cost}")
    
    @patch('app.services.subscription_service.StripeService')
    def test_process_usage_overage_with_billing(self, mock_stripe_service, app, subscription_service, test_subscription):
        """Test processing usage overage with billing."""
        subscription = test_subscription['subscription']
        entitlement = test_subscription['entitlement']
        
        # Mock invoice creation
        mock_invoice = Mock()
        mock_invoice.id = 1
        mock_stripe_service.return_value.create_invoice.return_value = mock_invoice
        
        # Process overage
        result = subscription_service.process_usage_overage(
            subscription.id, 'messages_per_month', 1200
        )
        
        # Verify results
        assert result['action'] == 'overage_billed'
        assert result['feature'] == 'messages_per_month'
        assert result['overage_amount'] == 200  # 1200 - 1000
        assert result['overage_cost'] == 2.00  # 200 * $0.01
        assert result['invoice_id'] == 1
        
        # Verify entitlement was updated
        entitlement.refresh()
        assert entitlement.used_value == 1200
        
        print(f"✓ Overage processed: {result['overage_amount']} units")
        print(f"✓ Overage cost: ${result['overage_cost']}")
        print(f"✓ Invoice created: {result['invoice_id']}")
    
    def test_process_usage_overage_within_limit(self, app, subscription_service, test_subscription):
        """Test processing usage when within limit."""
        subscription = test_subscription['subscription']
        
        # Process usage within limit
        result = subscription_service.process_usage_overage(
            subscription.id, 'messages_per_month', 800
        )
        
        # Verify no overage
        assert result['action'] == 'within_limit'
        assert result['feature'] == 'messages_per_month'
        assert result['usage'] == 800
        
        print(f"✓ Usage within limit: {result['usage']}")
    
    def test_process_usage_overage_unlimited(self, app, subscription_service):
        """Test processing usage for unlimited feature."""
        # Create unlimited subscription
        tenant = Tenant.create(name="Unlimited Co", domain="unlimited.co", settings={})
        plan = Plan.create(name="Unlimited", price=Decimal('299.99'), limits={'messages_per_month': -1})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=plan.id, status='active')
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=-1,  # Unlimited
            used_value=10000
        )
        
        # Process high usage
        result = subscription_service.process_usage_overage(
            subscription.id, 'messages_per_month', 10000
        )
        
        # Verify unlimited handling
        assert result['action'] == 'unlimited'
        assert result['feature'] == 'messages_per_month'
        
        print(f"✓ Unlimited feature handled: {result['action']}")
    
    def test_process_usage_overage_no_limit(self, app, subscription_service):
        """Test processing usage for feature with no limit."""
        # Create subscription without entitlement
        tenant = Tenant.create(name="No Limit Co", domain="nolimit.co", settings={})
        plan = Plan.create(name="No Limit", price=Decimal('99.99'), limits={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=plan.id, status='active')
        
        # Process usage for feature without entitlement
        result = subscription_service.process_usage_overage(
            subscription.id, 'messages_per_month', 5000
        )
        
        # Verify no limit handling
        assert result['action'] == 'no_limit'
        assert result['feature'] == 'messages_per_month'
        
        print(f"✓ No limit feature handled: {result['action']}")


class TestEntitlementManagement:
    """Test entitlement management functionality."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def test_plan(self, app):
        """Create test plan."""
        return Plan.create(
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
    
    def test_entitlement_creation_from_plan(self, app, test_plan):
        """Test creating entitlements from plan."""
        tenant = Tenant.create(name="Entitlement Co", domain="entitlement.co", settings={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=test_plan.id, status='active')
        
        # Create entitlements from plan
        entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, test_plan)
        
        # Verify entitlements created
        assert len(entitlements) == 4  # 4 limits in plan
        
        # Check each entitlement
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
        for ent in entitlements:
            print(f"  - {ent.feature}: 0/{ent.limit_value} ({ent.reset_frequency})")
    
    def test_entitlement_usage_increment(self, app, test_plan):
        """Test incrementing entitlement usage."""
        tenant = Tenant.create(name="Usage Co", domain="usage.co", settings={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=test_plan.id, status='active')
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=2000,
            used_value=0
        )
        
        # Test increment
        entitlement.increment_usage(100)
        assert entitlement.used_value == 100
        
        entitlement.increment_usage(50)
        assert entitlement.used_value == 150
        
        # Test large increment
        entitlement.increment_usage(1000)
        assert entitlement.used_value == 1150
        
        print(f"✓ Usage incremented: {entitlement.used_value}/{entitlement.limit_value}")
    
    def test_entitlement_usage_decrement(self, app, test_plan):
        """Test decrementing entitlement usage."""
        tenant = Tenant.create(name="Decrement Co", domain="decrement.co", settings={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=test_plan.id, status='active')
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=2000,
            used_value=500
        )
        
        # Test decrement
        entitlement.decrement_usage(100)
        assert entitlement.used_value == 400
        
        # Test decrement below zero (should not go negative)
        entitlement.decrement_usage(500)
        assert entitlement.used_value == 0
        
        print(f"✓ Usage decremented safely: {entitlement.used_value}")
    
    def test_entitlement_usage_reset(self, app, test_plan):
        """Test resetting entitlement usage."""
        tenant = Tenant.create(name="Reset Co", domain="reset.co", settings={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=test_plan.id, status='active')
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=2000,
            used_value=1500
        )
        
        # Test reset
        entitlement.reset_usage()
        assert entitlement.used_value == 0
        
        print(f"✓ Usage reset: {entitlement.used_value}/{entitlement.limit_value}")
    
    def test_entitlement_quota_checks(self, app, test_plan):
        """Test entitlement quota checking methods."""
        tenant = Tenant.create(name="Quota Co", domain="quota.co", settings={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=test_plan.id, status='active')
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=750
        )
        
        # Test quota methods
        assert entitlement.remaining_quota() == 250
        assert entitlement.usage_percentage == 75.0
        assert not entitlement.is_over_limit
        assert entitlement.can_use(100)
        assert entitlement.can_use(250)
        assert not entitlement.can_use(300)
        
        # Test at limit
        entitlement.used_value = 1000
        assert entitlement.remaining_quota() == 0
        assert entitlement.usage_percentage == 100.0
        assert not entitlement.is_over_limit
        assert not entitlement.can_use(1)
        
        # Test over limit
        entitlement.used_value = 1100
        assert entitlement.remaining_quota() == 0
        assert entitlement.usage_percentage == 110.0
        assert entitlement.is_over_limit
        assert not entitlement.can_use(1)
        
        print("✓ Quota checks:")
        print(f"  - At 75%: remaining={250}, can_use(100)={entitlement.can_use(100)}")
        print(f"  - At 100%: remaining={0}, over_limit={False}")
        print(f"  - At 110%: remaining={0}, over_limit={True}")
    
    def test_entitlement_unlimited_handling(self, app):
        """Test unlimited entitlement handling."""
        tenant = Tenant.create(name="Unlimited Co", domain="unlimited.co", settings={})
        plan = Plan.create(name="Unlimited", price=Decimal('299.99'), limits={'messages_per_month': -1})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=plan.id, status='active')
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=-1,  # Unlimited
            used_value=50000
        )
        
        # Test unlimited behavior
        assert entitlement.is_unlimited
        assert not entitlement.is_over_limit
        assert entitlement.usage_percentage == 0.0
        assert entitlement.remaining_quota() == -1
        assert entitlement.can_use(999999)
        
        print("✓ Unlimited entitlement:")
        print(f"  - Used: {entitlement.used_value}")
        print(f"  - Is unlimited: {entitlement.is_unlimited}")
        print(f"  - Can use large amount: {entitlement.can_use(999999)}")
    
    def test_entitlement_get_by_feature(self, app, test_plan):
        """Test getting entitlement by feature."""
        tenant = Tenant.create(name="Feature Co", domain="feature.co", settings={})
        subscription = Subscription.create(tenant_id=tenant.id, plan_id=test_plan.id, status='active')
        
        # Create entitlements
        entitlements = Entitlement.create_from_plan(tenant.id, subscription.id, test_plan)
        
        # Test getting by feature
        messages_entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
        assert messages_entitlement is not None
        assert messages_entitlement.feature == 'messages_per_month'
        assert messages_entitlement.limit_value == 2000
        
        # Test non-existent feature
        nonexistent = Entitlement.get_by_feature(subscription.id, 'nonexistent_feature')
        assert nonexistent is None
        
        print(f"✓ Found entitlement by feature: {messages_entitlement.feature}")
        print(f"✓ Non-existent feature returns None: {nonexistent is None}")


class TestUsageQuotaEnforcement:
    """Test comprehensive usage quota enforcement."""
    
    @pytest.fixture
    def app(self):
        """Create test app."""
        app = create_app('testing')
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def subscription_service(self, app):
        """Create subscription service."""
        return SubscriptionService()
    
    @pytest.fixture
    def test_tenant_with_overages(self, app):
        """Create tenant with multiple subscriptions and overages."""
        tenant = Tenant.create(name="Overage Tenant", domain="overage-tenant.com", settings={})
        
        # Create plan
        plan = Plan.create(
            name="Standard Plan",
            price=Decimal('79.99'),
            limits={
                'messages_per_month': 5000,
                'knowledge_documents': 200,
                'leads': 2000
            }
        )
        
        # Create subscription
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status='active',
            stripe_customer_id='cus_overage123'
        )
        
        # Create entitlements with overages
        entitlements = [
            Entitlement.create(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                feature='messages_per_month',
                limit_value=5000,
                used_value=6000  # Over by 1000
            ),
            Entitlement.create(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                feature='knowledge_documents',
                limit_value=200,
                used_value=180  # Within limit
            ),
            Entitlement.create(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                feature='leads',
                limit_value=2000,
                used_value=2500  # Over by 500
            )
        ]
        
        return {
            'tenant': tenant,
            'plan': plan,
            'subscription': subscription,
            'entitlements': entitlements
        }
    
    @patch('app.services.subscription_service.StripeService')
    def test_enforce_usage_quotas_with_overages(self, mock_stripe_service, app, subscription_service, test_tenant_with_overages):
        """Test enforcing usage quotas with overages."""
        tenant = test_tenant_with_overages['tenant']
        
        # Mock invoice creation
        mock_invoice = Mock()
        mock_invoice.id = 1
        mock_stripe_service.return_value.create_invoice.return_value = mock_invoice
        
        # Mock current usage calculation
        def mock_get_current_usage(subscription_id, feature):
            usage_map = {
                'messages_per_month': 6000,
                'knowledge_documents': 180,
                'leads': 2500
            }
            return usage_map.get(feature, 0)
        
        subscription_service._get_current_usage = mock_get_current_usage
        
        # Enforce quotas
        result = subscription_service.enforce_usage_quotas(tenant.id)
        
        # Verify results
        assert result['tenant_id'] == tenant.id
        assert result['enforced_count'] == 2  # 2 features over limit
        assert len(result['results']) == 2
        
        # Check enforcement results
        enforcement_results = {r['feature']: r for r in result['results']}
        
        # Messages overage
        messages_result = enforcement_results['messages_per_month']
        assert messages_result['current_usage'] == 6000
        assert messages_result['limit'] == 5000
        assert messages_result['overage_result']['action'] == 'overage_billed'
        assert messages_result['overage_result']['overage_amount'] == 1000
        
        # Leads overage
        leads_result = enforcement_results['leads']
        assert leads_result['current_usage'] == 2500
        assert leads_result['limit'] == 2000
        assert leads_result['overage_result']['action'] == 'overage_billed'
        assert leads_result['overage_result']['overage_amount'] == 500
        
        print(f"✓ Quota enforcement completed: {result['enforced_count']} overages")
        print(f"✓ Messages overage: {messages_result['overage_result']['overage_amount']}")
        print(f"✓ Leads overage: {leads_result['overage_result']['overage_amount']}")
    
    def test_enforce_usage_quotas_no_overages(self, app, subscription_service):
        """Test enforcing usage quotas with no overages."""
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
        
        # Mock current usage
        subscription_service._get_current_usage = lambda sid, feature: 2000
        
        # Enforce quotas
        result = subscription_service.enforce_usage_quotas(tenant.id)
        
        # Verify no enforcement needed
        assert result['tenant_id'] == tenant.id
        assert result['enforced_count'] == 0
        assert len(result['results']) == 0
        
        print(f"✓ No quota enforcement needed: {result['enforced_count']} overages")
    
    def test_enforce_usage_quotas_mixed_subscriptions(self, app, subscription_service):
        """Test enforcing usage quotas across multiple subscriptions."""
        tenant = Tenant.create(name="Multi Sub Tenant", domain="multi-sub.com", settings={})
        
        # Create multiple plans and subscriptions
        basic_plan = Plan.create(name="Basic", price=Decimal('29.99'), limits={'messages_per_month': 1000})
        pro_plan = Plan.create(name="Pro", price=Decimal('79.99'), limits={'messages_per_month': 5000})
        
        basic_sub = Subscription.create(tenant_id=tenant.id, plan_id=basic_plan.id, status='active')
        pro_sub = Subscription.create(tenant_id=tenant.id, plan_id=pro_plan.id, status='active')
        
        # Create entitlements
        Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=basic_sub.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=1200  # Over limit
        )
        
        Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=pro_sub.id,
            feature='messages_per_month',
            limit_value=5000,
            used_value=4000  # Within limit
        )
        
        # Mock current usage
        def mock_usage(subscription_id, feature):
            if subscription_id == basic_sub.id:
                return 1200
            elif subscription_id == pro_sub.id:
                return 4000
            return 0
        
        subscription_service._get_current_usage = mock_usage
        
        # Mock invoice creation
        with patch.object(subscription_service, '_create_overage_invoice') as mock_create_invoice:
            mock_invoice = Mock()
            mock_invoice.id = 1
            mock_create_invoice.return_value = mock_invoice
            
            # Enforce quotas
            result = subscription_service.enforce_usage_quotas(tenant.id)
            
            # Verify only basic subscription had overage
            assert result['enforced_count'] == 1
            assert len(result['results']) == 1
            assert result['results'][0]['subscription_id'] == basic_sub.id
            
            print(f"✓ Mixed subscriptions: {result['enforced_count']} overage from basic plan")


def run_comprehensive_usage_tracking_tests():
    """Run all comprehensive usage tracking tests."""
    print("=== Comprehensive Usage Tracking Tests ===\n")
    
    # Test classes to run
    test_classes = [
        TestUsageLimitMonitoring,
        TestOverageCalculation,
        TestEntitlementManagement,
        TestUsageQuotaEnforcement
    ]
    
    total_tests = 0
    passed_tests = 0
    
    for test_class in test_classes:
        print(f"\n--- {test_class.__name__} ---")
        
        # Get test methods
        test_methods = [method for method in dir(test_class) if method.startswith('test_')]
        
        for test_method in test_methods:
            total_tests += 1
            try:
                # Create test instance
                test_instance = test_class()
                
                # Run test with fixtures
                app = create_app('testing')
                with app.app_context():
                    db.create_all()
                    
                    # Get method and run it
                    method = getattr(test_instance, test_method)
                    
                    # Call with required fixtures
                    if hasattr(test_instance, 'subscription_service'):
                        service = SubscriptionService()
                        method(app, service)
                    else:
                        method(app)
                    
                    db.drop_all()
                
                print(f"✓ {test_method}")
                passed_tests += 1
                
            except Exception as e:
                print(f"✗ {test_method}: {str(e)}")
                import traceback
                traceback.print_exc()
    
    print(f"\n=== Results: {passed_tests}/{total_tests} tests passed ===")
    
    if passed_tests == total_tests:
        print("✓ All usage tracking tests passed!")
        return True
    else:
        print("✗ Some tests failed")
        return False


if __name__ == '__main__':
    success = run_comprehensive_usage_tracking_tests()
    sys.exit(0 if success else 1)