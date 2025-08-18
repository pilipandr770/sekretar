"""Unit tests for billing worker functionality."""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import stripe
from app import db
from app.models.billing import Plan, Subscription, UsageEvent, Entitlement
from app.models.tenant import Tenant
from app.workers.billing import (
    sync_stripe_usage,
    enforce_subscription_quotas,
    process_trial_expirations,
    handle_plan_upgrades
)


def test_sync_stripe_usage_success(app):
    """Test successful Stripe usage sync."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.flush()  # Get ID without committing
        
        # Create plan and subscription
        plan = Plan(
            name="Pro Plan",
            price=29.99,
            billing_interval="monthly",
            features={"ai_responses": True},
            limits={"messages_per_month": 1000},
            stripe_price_id="price_test123",
            is_active=True
        )
        db.session.add(plan)
        db.session.flush()
        
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_test123",
            status="active",
            current_period_start=(datetime.utcnow() - timedelta(days=15)).isoformat(),
            current_period_end=(datetime.utcnow() + timedelta(days=15)).isoformat()
        )
        db.session.add(subscription)
        db.session.commit()
        
        # Create usage events
        UsageEvent.record_usage(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            event_type="messages_sent",
            quantity=100
        )
        
        with patch('stripe.SubscriptionItem.create_usage_record') as mock_stripe:
            mock_stripe.return_value = Mock(id="ur_test123", timestamp=1234567890)
            
            result = sync_stripe_usage(
                tenant_id=tenant.id,
                subscription_id=subscription.id
            )
        
        assert result['subscription_id'] == subscription.id
        assert result['tenant_id'] == tenant.id
        assert result['usage_summary']['messages_sent'] == 100
        assert 'synced_at' in result


def test_enforce_subscription_quotas_no_violations(app):
    """Test quota enforcement with no violations."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Create plan and subscription
        plan = Plan(
            name="Pro Plan",
            price=29.99,
            billing_interval="monthly",
            limits={"messages_per_month": 1000},
            is_active=True
        )
        db.session.add(plan)
        db.session.flush()
        
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            current_period_start=(datetime.utcnow() - timedelta(days=15)).isoformat()
        )
        db.session.add(subscription)
        db.session.commit()
        
        # Create usage within limits
        UsageEvent.record_usage(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            event_type="messages_per_month",
            quantity=500  # Under limit of 1000
        )
        
        result = enforce_subscription_quotas(
            tenant_id=tenant.id,
            subscription_id=subscription.id
        )
        
        assert result['tenant_id'] == tenant.id
        assert len(result['enforcement_results']) == 1
        assert len(result['enforcement_results'][0]['quota_violations']) == 0


def test_enforce_subscription_quotas_with_violations(app):
    """Test quota enforcement with violations."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Create plan and subscription
        plan = Plan(
            name="Pro Plan",
            price=29.99,
            billing_interval="monthly",
            limits={"messages_per_month": 1000},
            is_active=True
        )
        db.session.add(plan)
        db.session.flush()
        
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active",
            current_period_start=(datetime.utcnow() - timedelta(days=15)).isoformat()
        )
        db.session.add(subscription)
        db.session.commit()
        
        # Create usage exceeding limits
        UsageEvent.record_usage(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            event_type="messages_per_month",
            quantity=1500  # Over limit of 1000
        )
        
        with patch('app.workers.billing._schedule_notification') as mock_notify:
            result = enforce_subscription_quotas(
                tenant_id=tenant.id,
                subscription_id=subscription.id
            )
        
        assert result['tenant_id'] == tenant.id
        violations = result['enforcement_results'][0]['quota_violations']
        assert len(violations) == 1
        assert violations[0]['feature'] == 'messages_per_month'
        assert violations[0]['overage'] == 500
        
        # Check notification was scheduled
        mock_notify.assert_called()


def test_sync_usage_subscription_not_found(app):
    """Test sync with non-existent subscription."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.commit()
        
        with pytest.raises(Exception) as exc_info:
            sync_stripe_usage(
                tenant_id=tenant.id,
                subscription_id=99999
            )
        
        assert "not found" in str(exc_info.value)


def test_handle_plan_upgrades_success(app):
    """Test successful plan upgrade."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Create plans
        old_plan = Plan(
            name="Basic Plan",
            price=9.99,
            billing_interval="monthly",
            limits={"messages_per_month": 500},
            stripe_price_id="price_basic123",
            is_active=True
        )
        db.session.add(old_plan)
        db.session.flush()
        
        new_plan = Plan(
            name="Pro Plan",
            price=29.99,
            billing_interval="monthly",
            limits={"messages_per_month": 2000},
            stripe_price_id="price_pro123",
            is_active=True
        )
        db.session.add(new_plan)
        db.session.flush()
        
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=old_plan.id,
            stripe_subscription_id="sub_test123",
            status="active"
        )
        db.session.add(subscription)
        db.session.commit()
        
        with patch('stripe.Subscription.modify') as mock_stripe:
            mock_stripe.return_value = Mock(
                id="sub_test123",
                status="active",
                current_period_start=1234567890,
                current_period_end=1237159890
            )
            
            with patch('app.workers.billing._schedule_notification') as mock_notify:
                result = handle_plan_upgrades(
                    tenant_id=tenant.id,
                    subscription_id=subscription.id,
                    new_plan_id=new_plan.id,
                    prorate=True
                )
        
        # Check subscription was updated
        db.session.refresh(subscription)
        assert subscription.plan_id == new_plan.id
        
        # Check results
        assert result['subscription_id'] == subscription.id
        assert result['new_plan'] == new_plan.name
        assert result['prorate'] is True
        
        # Check notification was scheduled
        mock_notify.assert_called()


@patch('stripe.Subscription.retrieve')
@patch('stripe.Customer.retrieve')
def test_process_trial_expirations_with_payment(mock_customer, mock_subscription, app):
    """Test trial expiration with valid payment method."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Create plan and trial subscription
        plan = Plan(
            name="Pro Plan",
            price=29.99,
            billing_interval="monthly",
            is_active=True
        )
        db.session.add(plan)
        db.session.flush()
        
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            stripe_subscription_id="sub_trial123",
            status="trialing",
            trial_end=(datetime.utcnow() - timedelta(days=1)).isoformat(),  # Expired
            current_period_start=datetime.utcnow().isoformat(),
            current_period_end=(datetime.utcnow() + timedelta(days=30)).isoformat()
        )
        db.session.add(subscription)
        db.session.commit()
        
        # Mock Stripe responses
        mock_subscription.return_value = Mock(customer="cus_test123")
        mock_customer.return_value = Mock(
            default_source="card_test123",
            invoice_settings=Mock(default_payment_method=None)
        )
        
        with patch('app.workers.billing._schedule_notification') as mock_notify:
            result = process_trial_expirations()
        
        # Check subscription was converted to active
        db.session.refresh(subscription)
        assert subscription.status == "active"
        
        # Check results
        assert result['processed_count'] == 1
        assert result['processing_results'][0]['action'] == 'converted_to_active'
        
        # Check notification was scheduled
        mock_notify.assert_called()


def test_handle_plan_upgrades_invalid_plan(app):
    """Test plan upgrade with invalid plan."""
    with app.app_context():
        # Create tenant
        tenant = Tenant(
            name="Test Company",
            domain="test.com",
            slug="test-company",
            settings={}
        )
        db.session.add(tenant)
        db.session.flush()
        
        # Create plan and subscription
        plan = Plan(
            name="Basic Plan",
            price=9.99,
            billing_interval="monthly",
            is_active=True
        )
        db.session.add(plan)
        db.session.flush()
        
        subscription = Subscription(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status="active"
        )
        db.session.add(subscription)
        db.session.commit()
        
        with pytest.raises(Exception) as exc_info:
            handle_plan_upgrades(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                new_plan_id=99999,
                prorate=True
            )
        
        assert "not found" in str(exc_info.value)