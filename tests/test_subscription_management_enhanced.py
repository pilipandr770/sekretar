"""Enhanced tests for subscription management functionality."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from app.models.billing import Subscription, Plan, Entitlement, UsageEvent
from app.models.tenant import Tenant
from app.services.subscription_service import SubscriptionService
from app.services.stripe_service import StripeService
from app.utils.exceptions import StripeError, ValidationError


class TestSubscriptionServiceEnhanced:
    """Enhanced tests for SubscriptionService."""
    
    @pytest.fixture
    def subscription_service(self):
        """Create SubscriptionService instance."""
        return SubscriptionService()
    
    @pytest.fixture
    def tenant(self, db_session):
        """Create test tenant."""
        return Tenant.create(
            name='Test Company',
            domain='test.com',
            slug='test-company'
        )
    
    @pytest.fixture
    def starter_plan(self, db_session):
        """Create starter plan."""
        return Plan.create(
            name='Starter',
            description='Perfect for small businesses',
            price=Decimal('29.00'),
            billing_interval='month',
            features={
                'channels': ['telegram', 'signal', 'widget'],
                'ai_responses': True,
                'crm': True,
                'calendar': True,
                'knowledge_base': True
            },
            limits={
                'users': 3,
                'messages_per_month': 1000,
                'knowledge_documents': 50,
                'leads': 500
            },
            stripe_price_id='price_starter123',
            stripe_product_id='prod_starter123'
        )
    
    @pytest.fixture
    def pro_plan(self, db_session):
        """Create pro plan."""
        return Plan.create(
            name='Pro',
            description='Advanced features for growing businesses',
            price=Decimal('79.00'),
            billing_interval='month',
            features={
                'channels': ['telegram', 'signal', 'widget', 'email'],
                'ai_responses': True,
                'crm': True,
                'calendar': True,
                'knowledge_base': True,
                'advanced_analytics': True,
                'kyb_monitoring': True
            },
            limits={
                'users': 10,
                'messages_per_month': 5000,
                'knowledge_documents': 200,
                'leads': 2000
            },
            stripe_price_id='price_pro123',
            stripe_product_id='prod_pro123'
        )
    
    @pytest.fixture
    def free_plan(self, db_session):
        """Create free plan."""
        return Plan.create(
            name='Free',
            description='Basic features for evaluation',
            price=Decimal('0.00'),
            billing_interval='month',
            features={
                'channels': ['widget'],
                'ai_responses': False
            },
            limits={
                'users': 1,
                'messages_per_month': 100,
                'knowledge_documents': 5,
                'leads': 50
            },
            stripe_price_id='price_free123',
            stripe_product_id='prod_free123'
        )
    
    def test_create_plan_success(self, subscription_service):
        """Test successful plan creation."""
        with patch.object(subscription_service.stripe_service, 'create_stripe_plan') as mock_stripe:
            mock_product = MagicMock(id='prod_test123')
            mock_price = MagicMock(id='price_test123')
            mock_stripe.return_value = (mock_product, mock_price)
            
            plan = subscription_service.create_plan(
                name='Test Plan',
                price=Decimal('49.99'),
                billing_interval='month',
                description='Test plan description',
                features={'ai_responses': True, 'crm': True},
                limits={'messages_per_month': 2000, 'users': 5}
            )
            
            assert plan.name == 'Test Plan'
            assert plan.price == Decimal('49.99')
            assert plan.billing_interval == 'month'
            assert plan.description == 'Test plan description'
            assert plan.features['ai_responses'] is True
            assert plan.limits['messages_per_month'] == 2000
            assert plan.stripe_price_id == 'price_test123'
            assert plan.stripe_product_id == 'prod_test123'
            assert plan.is_active is True
            assert plan.is_public is True
            
            mock_stripe.assert_called_once()
    
    def test_create_plan_validation_errors(self, subscription_service):
        """Test plan creation with validation errors."""
        # Test empty name
        with pytest.raises(ValidationError, match="Plan name must be at least 2 characters"):
            subscription_service.create_plan(
                name='',
                price=Decimal('29.99')
            )
        
        # Test negative price
        with pytest.raises(ValidationError, match="Plan price must be positive"):
            subscription_service.create_plan(
                name='Test Plan',
                price=Decimal('-10.00')
            )
        
        # Test invalid billing interval
        with pytest.raises(ValidationError, match="Billing interval must be 'month' or 'year'"):
            subscription_service.create_plan(
                name='Test Plan',
                price=Decimal('29.99'),
                billing_interval='weekly'
            )
        
        # Test invalid features type
        with pytest.raises(ValidationError, match="Features must be a dictionary"):
            subscription_service.create_plan(
                name='Test Plan',
                price=Decimal('29.99'),
                features='invalid'
            )
        
        # Test invalid limits type
        with pytest.raises(ValidationError, match="Limits must be a dictionary"):
            subscription_service.create_plan(
                name='Test Plan',
                price=Decimal('29.99'),
                limits='invalid'
            )
        
        # Test invalid limit value
        with pytest.raises(ValidationError, match="Limit 'users' must be a non-negative number"):
            subscription_service.create_plan(
                name='Test Plan',
                price=Decimal('29.99'),
                limits={'users': -5}
            )
    
    def test_create_plan_duplicate_name(self, subscription_service, starter_plan):
        """Test plan creation with duplicate name."""
        with pytest.raises(ValidationError, match="Plan with name 'Starter' already exists"):
            subscription_service.create_plan(
                name='Starter',
                price=Decimal('39.99')
            )
    
    def test_create_trial_subscription_success(self, subscription_service, tenant, starter_plan):
        """Test successful trial subscription creation."""
        with patch.object(subscription_service.stripe_service, 'create_customer') as mock_customer:
            with patch.object(subscription_service.stripe_service, 'create_trial_subscription') as mock_trial:
                with patch.object(subscription_service, '_schedule_trial_expiration_check'):
                    mock_customer.return_value = 'cus_test123'
                    
                    mock_subscription = Subscription(
                        id=1,
                        tenant_id=tenant.id,
                        plan_id=starter_plan.id,
                        stripe_subscription_id='sub_trial123',
                        stripe_customer_id='cus_test123',
                        status='trialing',
                        trial_start=datetime.utcnow().isoformat(),
                        trial_end=(datetime.utcnow() + timedelta(days=3)).isoformat()
                    )
                    mock_trial.return_value = mock_subscription
                    
                    subscription = subscription_service.create_trial_subscription(
                        tenant_id=tenant.id,
                        plan_id=starter_plan.id,
                        customer_email='test@example.com',
                        customer_name='Test User',
                        trial_days=3
                    )
                    
                    assert subscription.status == 'trialing'
                    assert subscription.stripe_subscription_id == 'sub_trial123'
                    assert subscription.tenant_id == tenant.id
                    assert subscription.plan_id == starter_plan.id
                    
                    mock_customer.assert_called_once()
                    mock_trial.assert_called_once()
    
    def test_create_trial_subscription_validation_errors(self, subscription_service, tenant, starter_plan):
        """Test trial subscription creation with validation errors."""
        # Test invalid trial days
        with pytest.raises(ValidationError, match="Trial days must be between 1 and 30"):
            subscription_service.create_trial_subscription(
                tenant_id=tenant.id,
                plan_id=starter_plan.id,
                customer_email='test@example.com',
                trial_days=0
            )
        
        with pytest.raises(ValidationError, match="Trial days must be between 1 and 30"):
            subscription_service.create_trial_subscription(
                tenant_id=tenant.id,
                plan_id=starter_plan.id,
                customer_email='test@example.com',
                trial_days=35
            )
        
        # Test invalid plan
        with pytest.raises(ValidationError, match="Invalid or inactive plan"):
            subscription_service.create_trial_subscription(
                tenant_id=tenant.id,
                plan_id=999,
                customer_email='test@example.com'
            )
    
    def test_create_trial_subscription_existing_active(self, subscription_service, tenant, starter_plan):
        """Test trial subscription creation when tenant already has active subscription."""
        # Create existing active subscription
        existing_subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_existing123',
            status='active'
        )
        
        with pytest.raises(ValidationError, match="Tenant already has an active subscription"):
            subscription_service.create_trial_subscription(
                tenant_id=tenant.id,
                plan_id=starter_plan.id,
                customer_email='test@example.com'
            )
    
    def test_handle_trial_expiration_convert_to_paid(self, subscription_service, tenant, starter_plan):
        """Test trial expiration with valid payment method."""
        # Create trial subscription
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_trial123',
            status='trialing',
            trial_start=datetime.utcnow().isoformat(),
            trial_end=(datetime.utcnow() - timedelta(hours=1)).isoformat()  # Expired
        )
        
        with patch.object(subscription_service, '_check_payment_method') as mock_payment:
            with patch.object(subscription_service, '_convert_trial_to_paid') as mock_convert:
                mock_payment.return_value = True
                mock_convert.return_value = {
                    'action': 'converted_to_paid',
                    'subscription_id': subscription.id,
                    'plan_name': starter_plan.name
                }
                
                result = subscription_service.handle_trial_expiration(subscription.id)
                
                assert result['action'] == 'converted_to_paid'
                assert result['subscription_id'] == subscription.id
                
                mock_payment.assert_called_once()
                mock_convert.assert_called_once()
    
    def test_handle_trial_expiration_downgrade_to_free(self, subscription_service, tenant, starter_plan, free_plan):
        """Test trial expiration without payment method - downgrade to free."""
        # Create trial subscription
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_trial123',
            status='trialing',
            trial_start=datetime.utcnow().isoformat(),
            trial_end=(datetime.utcnow() - timedelta(hours=1)).isoformat()  # Expired
        )
        
        with patch.object(subscription_service, '_check_payment_method') as mock_payment:
            with patch.object(subscription_service, '_handle_trial_without_payment') as mock_handle:
                mock_payment.return_value = False
                mock_handle.return_value = {
                    'action': 'downgraded_to_free',
                    'subscription_id': subscription.id,
                    'old_plan': starter_plan.name,
                    'new_plan': free_plan.name
                }
                
                result = subscription_service.handle_trial_expiration(subscription.id)
                
                assert result['action'] == 'downgraded_to_free'
                assert result['old_plan'] == starter_plan.name
                assert result['new_plan'] == free_plan.name
                
                mock_payment.assert_called_once()
                mock_handle.assert_called_once()
    
    def test_handle_trial_expiration_not_expired(self, subscription_service, tenant, starter_plan):
        """Test trial expiration check when trial is not yet expired."""
        # Create trial subscription that hasn't expired yet
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_trial123',
            status='trialing',
            trial_start=datetime.utcnow().isoformat(),
            trial_end=(datetime.utcnow() + timedelta(days=2)).isoformat()  # Not expired
        )
        
        result = subscription_service.handle_trial_expiration(subscription.id)
        
        assert result['action'] == 'not_expired'
        assert 'trial_end' in result
    
    def test_handle_trial_expiration_validation_errors(self, subscription_service, tenant, starter_plan):
        """Test trial expiration with validation errors."""
        # Test non-existent subscription
        with pytest.raises(ValidationError, match="Subscription 999 not found"):
            subscription_service.handle_trial_expiration(999)
        
        # Test non-trial subscription
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_active123',
            status='active'
        )
        
        with pytest.raises(ValidationError, match="Subscription is not in trial"):
            subscription_service.handle_trial_expiration(subscription.id)
    
    def test_process_usage_overage_within_limit(self, subscription_service, tenant, starter_plan):
        """Test usage overage processing when within limit."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        # Create entitlement
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=0
        )
        
        result = subscription_service.process_usage_overage(
            subscription.id,
            'messages_per_month',
            800  # Within limit
        )
        
        assert result['action'] == 'within_limit'
        assert result['feature'] == 'messages_per_month'
        assert result['usage'] == 800
    
    def test_process_usage_overage_with_billing(self, subscription_service, tenant, starter_plan):
        """Test usage overage processing with billing."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_test123',
            stripe_customer_id='cus_test123',
            status='active'
        )
        
        # Create entitlement
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=0
        )
        
        with patch.object(subscription_service, '_create_overage_invoice') as mock_invoice:
            mock_invoice.return_value = MagicMock(id=123)
            
            result = subscription_service.process_usage_overage(
                subscription.id,
                'messages_per_month',
                1500  # Over limit
            )
            
            assert result['action'] == 'overage_billed'
            assert result['feature'] == 'messages_per_month'
            assert result['overage_amount'] == 500
            assert result['overage_cost'] == 5.0  # 500 * $0.01
            assert result['invoice_id'] == 123
            
            # Check entitlement was updated
            entitlement.refresh()
            assert entitlement.used_value == 1500
            
            mock_invoice.assert_called_once()
    
    def test_process_usage_overage_unlimited(self, subscription_service, tenant, starter_plan):
        """Test usage overage processing for unlimited feature."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        # Create unlimited entitlement
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=-1,  # Unlimited
            used_value=0
        )
        
        result = subscription_service.process_usage_overage(
            subscription.id,
            'messages_per_month',
            10000  # High usage
        )
        
        assert result['action'] == 'unlimited'
        assert result['feature'] == 'messages_per_month'
    
    def test_process_usage_overage_no_limit(self, subscription_service, tenant, starter_plan):
        """Test usage overage processing when no entitlement exists."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        result = subscription_service.process_usage_overage(
            subscription.id,
            'nonexistent_feature',
            1000
        )
        
        assert result['action'] == 'no_limit'
        assert result['feature'] == 'nonexistent_feature'
    
    def test_upgrade_subscription_success(self, subscription_service, tenant, starter_plan, pro_plan):
        """Test successful subscription upgrade."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        # Create entitlements for starter plan
        Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000
        )
        
        with patch.object(subscription_service.stripe_service, 'update_subscription') as mock_update:
            with patch.object(subscription_service, '_update_entitlements_to_plan') as mock_entitlements:
                mock_update.return_value = subscription
                
                result = subscription_service.upgrade_subscription(
                    subscription.id,
                    pro_plan.id,
                    prorate=True
                )
                
                assert result['subscription_id'] == subscription.id
                assert result['old_plan'] == starter_plan.name
                assert result['new_plan'] == pro_plan.name
                assert result['prorate'] is True
                assert 'upgraded_at' in result
                
                mock_update.assert_called_once()
                mock_entitlements.assert_called_once()
    
    def test_upgrade_subscription_validation_errors(self, subscription_service):
        """Test subscription upgrade with validation errors."""
        # Test non-existent subscription
        with pytest.raises(ValidationError, match="Subscription 999 not found"):
            subscription_service.upgrade_subscription(999, 1)
        
        # Test invalid new plan
        subscription = Subscription.create(
            tenant_id=1,
            plan_id=1,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        with pytest.raises(ValidationError, match="Invalid or inactive new plan"):
            subscription_service.upgrade_subscription(subscription.id, 999)
    
    def test_enforce_usage_quotas_success(self, subscription_service, tenant, starter_plan):
        """Test successful usage quota enforcement."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=starter_plan.id,
            stripe_subscription_id='sub_test123',
            status='active'
        )
        
        # Create entitlement with usage over limit
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=0
        )
        
        with patch.object(subscription_service, '_get_current_usage') as mock_usage:
            with patch.object(subscription_service, 'process_usage_overage') as mock_overage:
                mock_usage.return_value = 1500  # Over limit
                mock_overage.return_value = {
                    'action': 'overage_billed',
                    'overage_amount': 500
                }
                
                result = subscription_service.enforce_usage_quotas(tenant.id)
                
                assert result['tenant_id'] == tenant.id
                assert result['enforced_count'] == 1
                assert len(result['results']) == 1
                assert result['results'][0]['subscription_id'] == subscription.id
                assert result['results'][0]['feature'] == 'messages_per_month'
                assert result['results'][0]['current_usage'] == 1500
                assert result['results'][0]['limit'] == 1000
                
                mock_usage.assert_called_once()
                mock_overage.assert_called_once()


class TestSubscriptionManagementIntegration:
    """Integration tests for subscription management."""
    
    @pytest.fixture
    def tenant(self, db_session):
        """Create test tenant."""
        return Tenant.create(
            name='Integration Test Company',
            domain='integration.com',
            slug='integration-test'
        )
    
    def test_complete_subscription_lifecycle(self, tenant, db_session):
        """Test complete subscription lifecycle from trial to paid to upgrade."""
        subscription_service = SubscriptionService()
        
        # Create plans
        starter_plan = Plan.create(
            name='Starter',
            price=Decimal('29.00'),
            limits={'messages_per_month': 1000},
            stripe_price_id='price_starter123'
        )
        
        pro_plan = Plan.create(
            name='Pro',
            price=Decimal('79.00'),
            limits={'messages_per_month': 5000},
            stripe_price_id='price_pro123'
        )
        
        with patch.object(subscription_service.stripe_service, 'create_customer') as mock_customer:
            with patch.object(subscription_service.stripe_service, 'create_trial_subscription') as mock_trial:
                with patch.object(subscription_service, '_schedule_trial_expiration_check'):
                    # Step 1: Create trial subscription
                    mock_customer.return_value = 'cus_test123'
                    
                    trial_subscription = Subscription(
                        id=1,
                        tenant_id=tenant.id,
                        plan_id=starter_plan.id,
                        stripe_subscription_id='sub_trial123',
                        status='trialing'
                    )
                    mock_trial.return_value = trial_subscription
                    
                    subscription = subscription_service.create_trial_subscription(
                        tenant_id=tenant.id,
                        plan_id=starter_plan.id,
                        customer_email='test@integration.com',
                        trial_days=3
                    )
                    
                    assert subscription.status == 'trialing'
                    
                    # Step 2: Convert trial to paid
                    with patch.object(subscription_service, '_check_payment_method') as mock_payment:
                        with patch.object(subscription_service, '_convert_trial_to_paid') as mock_convert:
                            mock_payment.return_value = True
                            mock_convert.return_value = {
                                'action': 'converted_to_paid',
                                'subscription_id': subscription.id
                            }
                            
                            trial_result = subscription_service.handle_trial_expiration(subscription.id)
                            assert trial_result['action'] == 'converted_to_paid'
                    
                    # Step 3: Upgrade subscription
                    with patch.object(subscription_service.stripe_service, 'update_subscription') as mock_update:
                        with patch.object(subscription_service, '_update_entitlements_to_plan'):
                            mock_update.return_value = subscription
                            
                            upgrade_result = subscription_service.upgrade_subscription(
                                subscription.id,
                                pro_plan.id
                            )
                            
                            assert upgrade_result['old_plan'] == starter_plan.name
                            assert upgrade_result['new_plan'] == pro_plan.name
    
    def test_usage_overage_billing_flow(self, tenant, db_session):
        """Test complete usage overage billing flow."""
        subscription_service = SubscriptionService()
        
        # Create plan and subscription
        plan = Plan.create(
            name='Test Plan',
            price=Decimal('29.00'),
            limits={'messages_per_month': 1000},
            stripe_price_id='price_test123'
        )
        
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            stripe_subscription_id='sub_test123',
            stripe_customer_id='cus_test123',
            status='active'
        )
        
        # Create entitlement
        entitlement = Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=800
        )
        
        # Record usage events to simulate overage
        for i in range(300):  # This will put us over the 1000 limit
            UsageEvent.record_usage(
                tenant_id=tenant.id,
                subscription_id=subscription.id,
                event_type='messages_per_month',
                quantity=1
            )
        
        with patch.object(subscription_service, '_create_overage_invoice') as mock_invoice:
            mock_invoice.return_value = MagicMock(id=123)
            
            # Process overage
            result = subscription_service.process_usage_overage(
                subscription.id,
                'messages_per_month',
                1100  # Over limit
            )
            
            assert result['action'] == 'overage_billed'
            assert result['overage_amount'] == 100
            assert result['overage_cost'] == 1.0  # 100 * $0.01
            
            # Verify entitlement was updated
            entitlement.refresh()
            assert entitlement.used_value == 1100