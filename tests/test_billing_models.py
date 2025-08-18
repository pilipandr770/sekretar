"""Test billing and subscription models."""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from app.models.tenant import Tenant
from app.models.user import User
from app.models.billing import Plan, Subscription, UsageEvent, Entitlement, Invoice
from app import db


class TestPlan:
    """Test Plan model."""
    
    def test_create_plan(self, app):
        """Test plan creation."""
        with app.app_context():
            plan = Plan(
                name="Starter",
                description="Basic plan for small businesses",
                price=Decimal('29.00'),
                billing_interval="month"
            )
            plan.save()
            
            assert plan.id is not None
            assert plan.name == "Starter"
            assert plan.price == Decimal('29.00')
            assert plan.billing_interval == "month"
            assert plan.is_active is True
    
    def test_plan_features_and_limits(self, app):
        """Test plan features and limits management."""
        with app.app_context():
            plan = Plan(
                name="Pro",
                price=Decimal('79.00')
            )
            plan.save()
            
            # Test setting features
            plan.set_feature("ai_responses", True)
            plan.set_feature("crm", True)
            plan.set_feature("advanced_analytics", False)
            plan.save()
            
            assert plan.has_feature("ai_responses") is True
            assert plan.has_feature("crm") is True
            assert plan.has_feature("advanced_analytics") is False
            assert plan.has_feature("nonexistent") is False
            
            # Test setting limits
            plan.set_limit("users", 10)
            plan.set_limit("messages_per_month", 5000)
            plan.save()
            
            assert plan.get_limit("users") == 10
            assert plan.get_limit("messages_per_month") == 5000
            assert plan.get_limit("nonexistent") is None
    
    def test_plan_price_calculations(self, app):
        """Test plan price calculations."""
        with app.app_context():
            # Monthly plan
            monthly_plan = Plan(
                name="Monthly",
                price=Decimal('50.00'),
                billing_interval="month"
            )
            monthly_plan.save()
            
            assert monthly_plan.get_monthly_price() == 50.00
            assert monthly_plan.get_yearly_price() == 600.00
            
            # Yearly plan
            yearly_plan = Plan(
                name="Yearly",
                price=Decimal('500.00'),
                billing_interval="year"
            )
            yearly_plan.save()
            
            assert yearly_plan.get_yearly_price() == 500.00
            assert abs(yearly_plan.get_monthly_price() - 41.67) < 0.01  # 500/12
    
    def test_create_default_plans(self, app):
        """Test creating default plans."""
        with app.app_context():
            plans = Plan.create_default_plans()
            
            assert len(plans) == 4
            
            plan_names = [plan.name for plan in plans]
            assert "Starter" in plan_names
            assert "Pro" in plan_names
            assert "Team" in plan_names
            assert "Enterprise" in plan_names
            
            # Check that plans have proper features and limits
            starter = next(plan for plan in plans if plan.name == "Starter")
            assert starter.has_feature("ai_responses") is True
            assert starter.get_limit("users") == 3
            assert starter.get_limit("messages_per_month") == 1000
            
            enterprise = next(plan for plan in plans if plan.name == "Enterprise")
            assert enterprise.get_limit("users") == -1  # Unlimited


class TestSubscription:
    """Test Subscription model."""
    
    def test_create_subscription(self, app):
        """Test subscription creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Starter", price=Decimal('29.00'))
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                stripe_subscription_id="sub_test123"
            )
            subscription.save()
            
            assert subscription.id is not None
            assert subscription.tenant_id == tenant.id
            assert subscription.plan_id == plan.id
            assert subscription.status == "active"
            assert subscription.is_active is True
    
    def test_subscription_status_properties(self, app):
        """Test subscription status properties."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.save()
            
            # Test active subscription
            active_sub = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            active_sub.save()
            
            assert active_sub.is_active is True
            assert active_sub.is_trial is False
            assert active_sub.is_canceled is False
            
            # Test trial subscription
            trial_sub = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="trialing"
            )
            trial_sub.save()
            
            assert trial_sub.is_active is True
            assert trial_sub.is_trial is True
            assert trial_sub.is_canceled is False
            
            # Test canceled subscription
            canceled_sub = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="canceled"
            )
            canceled_sub.save()
            
            assert canceled_sub.is_active is False
            assert canceled_sub.is_canceled is True
    
    def test_subscription_cancellation(self, app):
        """Test subscription cancellation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            # Test cancel at period end
            subscription.cancel(at_period_end=True)
            subscription.save()
            
            assert subscription.cancel_at_period_end is True
            assert subscription.status == "active"  # Still active until period end
            
            # Test immediate cancellation
            subscription.cancel(at_period_end=False)
            subscription.save()
            
            assert subscription.status == "canceled"
            assert subscription.canceled_at is not None
    
    def test_subscription_feature_access(self, app):
        """Test subscription feature access."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.set_feature("ai_responses", True)
            plan.set_feature("advanced_analytics", False)
            plan.set_limit("users", 5)
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            # Test feature access
            assert subscription.has_feature("ai_responses") is True
            assert subscription.has_feature("advanced_analytics") is False
            
            # Test limit checking
            assert subscription.get_limit("users") == 5
            assert subscription.is_within_limit("users", 3) is True
            assert subscription.is_within_limit("users", 7) is False


class TestUsageEvent:
    """Test UsageEvent model."""
    
    def test_record_usage_event(self, app):
        """Test recording usage events."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            # Record usage event
            usage_event = UsageEvent.record_usage(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                event_type="message_sent",
                quantity=5,
                channel="telegram"
            )
            
            assert usage_event.id is not None
            assert usage_event.event_type == "message_sent"
            assert usage_event.quantity == 5
            assert usage_event.get_metadata("channel") == "telegram"
    
    def test_usage_aggregation(self, app):
        """Test usage aggregation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            # Record multiple usage events
            start_time = datetime.utcnow()
            
            for i in range(5):
                UsageEvent.record_usage(
                    tenant_id=tenant.id,
                    subscription_id=subscription.id,
                    event_type="message_sent",
                    quantity=2
                )
            
            end_time = datetime.utcnow()
            
            # Test total usage
            total_usage = UsageEvent.get_total_usage(
                subscription_id=subscription.id,
                event_type="message_sent",
                start_date=start_time.isoformat(),
                end_date=end_time.isoformat()
            )
            
            assert total_usage == 10  # 5 events * 2 quantity each


class TestEntitlement:
    """Test Entitlement model."""
    
    def test_create_entitlement(self, app):
        """Test entitlement creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            entitlement = Entitlement(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                feature="messages_per_month",
                limit_value=1000,
                used_value=250
            )
            entitlement.save()
            
            assert entitlement.id is not None
            assert entitlement.feature == "messages_per_month"
            assert entitlement.limit_value == 1000
            assert entitlement.used_value == 250
    
    def test_entitlement_usage_tracking(self, app):
        """Test entitlement usage tracking."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            entitlement = Entitlement(
                tenant_id=tenant.id,
                feature="users",
                limit_value=10,
                used_value=5
            )
            entitlement.save()
            
            # Test usage properties
            assert entitlement.is_unlimited is False
            assert entitlement.is_over_limit is False
            assert entitlement.usage_percentage == 50.0
            assert entitlement.remaining_quota() == 5
            
            # Test usage operations
            assert entitlement.can_use(3) is True
            assert entitlement.can_use(6) is False
            
            entitlement.increment_usage(3)
            entitlement.save()
            
            assert entitlement.used_value == 8
            assert entitlement.remaining_quota() == 2
            
            entitlement.decrement_usage(2)
            entitlement.save()
            
            assert entitlement.used_value == 6
    
    def test_unlimited_entitlement(self, app):
        """Test unlimited entitlement."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            entitlement = Entitlement(
                tenant_id=tenant.id,
                feature="storage",
                limit_value=-1,  # Unlimited
                used_value=1000000
            )
            entitlement.save()
            
            assert entitlement.is_unlimited is True
            assert entitlement.is_over_limit is False
            assert entitlement.can_use(999999) is True
            assert entitlement.remaining_quota() == -1
    
    def test_create_entitlements_from_plan(self, app):
        """Test creating entitlements from plan."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.set_limit("users", 5)
            plan.set_limit("messages_per_month", 1000)
            plan.set_limit("storage", -1)  # Unlimited
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            entitlements = Entitlement.create_from_plan(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                plan=plan
            )
            
            assert len(entitlements) == 3
            
            # Check specific entitlements
            users_entitlement = next(e for e in entitlements if e.feature == "users")
            assert users_entitlement.limit_value == 5
            assert users_entitlement.reset_frequency == "never"
            
            messages_entitlement = next(e for e in entitlements if e.feature == "messages_per_month")
            assert messages_entitlement.limit_value == 1000
            assert messages_entitlement.reset_frequency == "monthly"
            
            storage_entitlement = next(e for e in entitlements if e.feature == "storage")
            assert storage_entitlement.limit_value == -1
            assert storage_entitlement.is_unlimited is True


class TestInvoice:
    """Test Invoice model."""
    
    def test_create_invoice(self, app):
        """Test invoice creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            plan = Plan(name="Test", price=Decimal('50.00'))
            plan.save()
            
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active"
            )
            subscription.save()
            
            invoice = Invoice(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                stripe_invoice_id="in_test123",
                amount_total=Decimal('50.00'),
                currency="USD",
                status="open"
            )
            invoice.save()
            
            assert invoice.id is not None
            assert invoice.amount_total == Decimal('50.00')
            assert invoice.status == "open"
            assert invoice.is_paid is False
    
    def test_invoice_payment_tracking(self, app):
        """Test invoice payment tracking."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            invoice = Invoice(
                tenant_id=tenant.id,
                amount_total=Decimal('100.00'),
                amount_paid=Decimal('30.00'),
                status="open"
            )
            invoice.save()
            
            # Test amount due calculation
            assert invoice.amount_due == 70.00
            assert invoice.is_paid is False
            
            # Test marking as paid
            invoice.mark_as_paid()
            invoice.save()
            
            assert invoice.status == "paid"
            assert invoice.amount_paid == invoice.amount_total
            assert invoice.paid_at is not None
            assert invoice.is_paid is True
            assert invoice.amount_due == 0.00
    
    def test_invoice_overdue_check(self, app):
        """Test invoice overdue checking."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Create overdue invoice
            past_date = (datetime.utcnow() - timedelta(days=5)).isoformat()
            overdue_invoice = Invoice(
                tenant_id=tenant.id,
                amount_total=Decimal('50.00'),
                status="open",
                due_date=past_date
            )
            overdue_invoice.save()
            
            assert overdue_invoice.is_overdue is True
            
            # Create future invoice
            future_date = (datetime.utcnow() + timedelta(days=5)).isoformat()
            future_invoice = Invoice(
                tenant_id=tenant.id,
                amount_total=Decimal('50.00'),
                status="open",
                due_date=future_date
            )
            future_invoice.save()
            
            assert future_invoice.is_overdue is False
            
            # Paid invoices are never overdue
            overdue_invoice.mark_as_paid()
            overdue_invoice.save()
            
            assert overdue_invoice.is_overdue is False


class TestBillingIntegration:
    """Test billing model integration."""
    
    def test_complete_subscription_workflow(self, app):
        """Test complete subscription workflow."""
        with app.app_context():
            # Create tenant and plan
            tenant = Tenant(name="Test Company", slug="test-company")
            tenant.save()
            
            plan = Plan(name="Pro", price=Decimal('79.00'))
            plan.set_feature("ai_responses", True)
            plan.set_limit("users", 10)
            plan.set_limit("messages_per_month", 5000)
            plan.save()
            
            # Create subscription
            subscription = Subscription(
                tenant_id=tenant.id,
                plan_id=plan.id,
                status="active",
                stripe_subscription_id="sub_test123"
            )
            subscription.save()
            
            # Create entitlements
            entitlements = Entitlement.create_from_plan(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                plan=plan
            )
            
            # Record usage
            usage_event = UsageEvent.record_usage(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                event_type="message_sent",
                quantity=100
            )
            
            # Update entitlement usage
            messages_entitlement = next(e for e in entitlements if e.feature == "messages_per_month")
            messages_entitlement.increment_usage(100)
            messages_entitlement.save()
            
            # Create invoice
            invoice = Invoice(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                amount_total=plan.price,
                status="paid"
            )
            invoice.mark_as_paid()
            invoice.save()
            
            # Verify everything is connected
            assert subscription.has_feature("ai_responses") is True
            assert subscription.is_within_limit("users", 5) is True
            assert messages_entitlement.used_value == 100
            assert messages_entitlement.remaining_quota() == 4900
            assert invoice.is_paid is True
            
            # Test relationships
            assert len(subscription.usage_events) == 1
            assert len(subscription.entitlements) == 2
            assert subscription.usage_events[0].event_type == "message_sent"