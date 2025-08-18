"""
Complete unit tests for subscription management functionality.
Tests all requirements for task 9.2: Create subscription management.
"""

import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from app.models.billing import Plan, Subscription, UsageEvent, Entitlement
from app.services.subscription_service import SubscriptionService
from app.utils.exceptions import ValidationError, StripeError


class TestSubscriptionManagementComplete:
    """Complete tests for subscription management functionality."""
    
    @pytest.fixture
    def subscription_service(self, app):
        """Create subscription service instance."""
        with app.app_context():
            return SubscriptionService()
    
    @pytest.fixture
    def basic_plan(self, db_session):
        """Create basic plan for testing."""
        return Plan.create(
            name='Basic Plan',
            price=Decimal('29.99'),
            billing_interval='month',
            features={'ai_responses': True, 'crm': True},
            limits={'users': 5, 'messages_per_month': 1000}
        )
    
    @pytest.fixture
    def pro_plan(self, db_session):
        """Create pro plan for testing."""
        return Plan.create(
            name='Pro Plan',
            price=Decimal('79.99'),
            billing_interval='month',
            features={'ai_responses': True, 'crm': True, 'advanced_analytics': True},
            limits={'users': 15, 'messages_per_month': 5000}
        )
    
    def test_plan_creation_and_subscription_handling(self, subscription_service, tenant):
        """Test plan creation and subscription handling."""
        # Test plan creation
        with patch.object(subscription_service.stripe_service, 'create_stripe_plan') as mock_stripe:
            mock_stripe.return_value = (
                MagicMock(id='prod_test'),
                MagicMock(id='price_test')
            )
            
            plan = subscription_service.create_plan(
                name="Test Plan",
                price=Decimal("29.99"),
                billing_interval="month",
                features={'ai_responses': True},
                limits={'users': 5}
            )
            
            assert plan.name == "Test Plan"
            assert plan.price == Decimal("29.99")
            assert plan.features['ai_responses'] is True
            assert plan.limits['users'] == 5
            mock_stripe.assert_called_once()
    
    def test_trial_management_and_automatic_transitions(self, subscription_service, tenant, basic_plan):
        """Test trial management and automatic plan transitions."""
        # Test trial subscription creation
        with patch.object(subscription_service.stripe_service, 'create_customer') as mock_customer:
            with patch.object(subscription_service.stripe_service, 'create_trial_subscription') as mock_trial:
                mock_customer.return_value = 'cus_test'
                mock_trial.return_value = Subscription.create(
                    tenant_id=tenant.id,
                    plan_id=basic_plan.id,
                    status='trialing',
                    trial_start=datetime.utcnow().isoformat(),
                    trial_end=(datetime.utcnow() + timedelta(days=3)).isoformat()
                )
                
                subscription = subscription_service.create_trial_subscription(
                    tenant_id=tenant.id,
                    plan_id=basic_plan.id,
                    customer_email="test@example.com",
                    trial_days=3
                )
                
                assert subscription.is_trial
                assert subscription.status == 'trialing'
                mock_customer.assert_called_once()
                mock_trial.assert_called_once()
        
        # Test trial expiration handling
        subscription.trial_end = (datetime.utcnow() - timedelta(hours=1)).isoformat()
        subscription.save()
        
        with patch.object(subscription_service, '_check_payment_method') as mock_payment:
            mock_payment.return_value = True
            
            result = subscription_service.handle_trial_expiration(subscription.id)
            
            assert result['action'] == 'converted_to_paid'
            subscription.refresh()
            assert subscription.status == 'active'
    
    def test_usage_metering_and_overage_billing(self, subscription_service, tenant, basic_plan):
        """Test usage metering and overage billing."""
        # Create subscription with entitlements
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='active'
        )
        
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=0
        )
        
        # Test usage recording
        usage_event = UsageEvent.record_usage(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            event_type='messages_per_month',
            quantity=50
        )
        
        assert usage_event.event_type == 'messages_per_month'
        assert usage_event.quantity == 50
        
        # Test overage processing
        with patch.object(subscription_service, '_create_overage_invoice') as mock_invoice:
            mock_invoice.return_value = MagicMock(id=1)
            
            result = subscription_service.process_usage_overage(
                subscription_id=subscription.id,
                feature='messages_per_month',
                current_usage=1200  # Over the 1000 limit
            )
            
            assert result['action'] == 'overage_billed'
            assert result['overage_amount'] == 200
            mock_invoice.assert_called_once()
    
    def test_subscription_upgrade_downgrade(self, subscription_service, tenant, basic_plan, pro_plan):
        """Test subscription upgrade and downgrade functionality."""
        # Create subscription
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='active'
        )
        
        # Test upgrade
        with patch.object(subscription_service.stripe_service, 'update_subscription') as mock_update:
            mock_update.return_value = subscription
            
            result = subscription_service.upgrade_subscription(
                subscription_id=subscription.id,
                new_plan_id=pro_plan.id,
                prorate=True
            )
            
            assert result['old_plan'] == 'Basic Plan'
            assert result['new_plan'] == 'Pro Plan'
            assert result['prorate'] is True
            mock_update.assert_called_once()
    
    def test_quota_enforcement(self, subscription_service, tenant, basic_plan):
        """Test usage quota enforcement."""
        # Create subscription with entitlements
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='active'
        )
        
        # Create entitlement
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=1200  # Over limit
        )
        
        # Test quota enforcement
        with patch.object(subscription_service, '_get_current_usage') as mock_usage:
            mock_usage.return_value = 1200
            
            result = subscription_service.enforce_usage_quotas(tenant_id=tenant.id)
            
            assert result['tenant_id'] == tenant.id
            assert len(result['enforcement_results']) > 0
            
            enforcement_result = result['enforcement_results'][0]
            assert enforcement_result['subscription_id'] == subscription.id
            assert 'quota_violations' in enforcement_result
    
    def test_plan_validation(self, subscription_service):
        """Test plan creation validation."""
        # Test invalid plan name
        with pytest.raises(ValidationError, match="Plan name must be at least 2 characters"):
            subscription_service.create_plan(
                name="A",
                price=Decimal("29.99")
            )
        
        # Test invalid price
        with pytest.raises(ValidationError, match="Plan price must be positive"):
            subscription_service.create_plan(
                name="Test Plan",
                price=Decimal("-10.00")
            )
        
        # Test invalid billing interval
        with pytest.raises(ValidationError, match="Billing interval must be 'month' or 'year'"):
            subscription_service.create_plan(
                name="Test Plan",
                price=Decimal("29.99"),
                billing_interval="weekly"
            )
    
    def test_trial_validation(self, subscription_service, tenant, basic_plan):
        """Test trial subscription validation."""
        # Test invalid trial days
        with pytest.raises(ValidationError, match="Trial days must be between 1 and 30"):
            subscription_service.create_trial_subscription(
                tenant_id=tenant.id,
                plan_id=basic_plan.id,
                customer_email="test@example.com",
                trial_days=35
            )
        
        # Test duplicate active subscription
        Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='active'
        )
        
        with pytest.raises(ValidationError, match="Tenant already has an active subscription"):
            subscription_service.create_trial_subscription(
                tenant_id=tenant.id,
                plan_id=basic_plan.id,
                customer_email="test@example.com",
                trial_days=3
            )
    
    def test_entitlement_functionality(self, tenant, basic_plan):
        """Test entitlement model functionality."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='active'
        )
        
        # Test entitlement creation
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=500
        )
        
        # Test properties
        assert not entitlement.is_unlimited
        assert not entitlement.is_over_limit
        assert entitlement.usage_percentage == 50.0
        assert entitlement.remaining_quota() == 500
        
        # Test usage increment
        entitlement.increment_usage(100)
        assert entitlement.used_value == 600
        
        # Test can_use
        assert entitlement.can_use(300)
        assert not entitlement.can_use(500)  # Would exceed limit
        
        # Test refresh method
        entitlement.refresh()
        assert entitlement.used_value == 600
    
    def test_usage_event_functionality(self, tenant, basic_plan):
        """Test usage event model functionality."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='active'
        )
        
        # Test usage recording
        event = UsageEvent.record_usage(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            event_type='messages_sent',
            quantity=10,
            source='api'
        )
        
        assert event.event_type == 'messages_sent'
        assert event.quantity == 10
        assert event.get_metadata('source') == 'api'
        
        # Test usage aggregation
        start_date = datetime.utcnow().isoformat()
        end_date = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        total_usage = UsageEvent.get_total_usage(
            subscription_id=subscription.id,
            event_type='messages_sent',
            start_date=start_date,
            end_date=end_date
        )
        
        assert total_usage == 10
    
    def test_stripe_error_handling(self, subscription_service):
        """Test Stripe error handling."""
        with patch.object(subscription_service.stripe_service, 'create_stripe_plan') as mock_stripe:
            mock_stripe.side_effect = StripeError("Stripe API error")
            
            with pytest.raises(StripeError, match="Stripe API error"):
                subscription_service.create_plan(
                    name="Test Plan",
                    price=Decimal("29.99")
                )
    
    def test_subscription_status_properties(self, tenant, basic_plan):
        """Test subscription status properties."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            status='trialing',
            trial_start=datetime.utcnow().isoformat(),
            trial_end=(datetime.utcnow() + timedelta(days=3)).isoformat()
        )
        
        assert subscription.is_active
        assert subscription.is_trial
        assert not subscription.is_canceled
        assert not subscription.is_past_due
        
        # Test cancellation
        subscription.cancel(at_period_end=False)
        assert subscription.is_canceled
        
        # Test reactivation
        subscription.reactivate()
        assert not subscription.is_canceled
        assert subscription.status == 'active'
    
    def test_plan_features_and_limits(self, basic_plan):
        """Test plan features and limits functionality."""
        # Test feature access
        assert basic_plan.has_feature('ai_responses')
        assert not basic_plan.has_feature('advanced_analytics')
        
        # Test limit access
        assert basic_plan.get_limit('users') == 5
        assert basic_plan.get_limit('messages_per_month') == 1000
        assert basic_plan.get_limit('nonexistent') is None
        
        # Test feature and limit modification
        basic_plan.set_feature('new_feature', True)
        basic_plan.set_limit('new_limit', 100)
        
        assert basic_plan.get_feature('new_feature') is True
        assert basic_plan.get_limit('new_limit') == 100
        
        # Test price calculations
        assert basic_plan.get_monthly_price() == 29.99
        assert basic_plan.get_yearly_price() == 359.88  # 29.99 * 12