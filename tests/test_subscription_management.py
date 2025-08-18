"""Tests for subscription management functionality."""
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal
from datetime import datetime, timedelta
from app.models.billing import Subscription, Plan, Entitlement, UsageEvent
from app.models.tenant import Tenant
from app.services.stripe_service import StripeService
from app.utils.exceptions import StripeError, ValidationError


class TestSubscriptionManagement:
    """Test subscription management features."""
    
    @pytest.fixture
    def tenant(self, db_session):
        """Create test tenant."""
        tenant = Tenant.create(
            name='Test Company',
            domain='test.com',
            slug='test-company'
        )
        return tenant
    
    @pytest.fixture
    def basic_plan(self, db_session):
        """Create basic test plan."""
        plan = Plan.create(
            name='Basic Plan',
            price=Decimal('29.00'),
            billing_interval='month',
            features={'ai_responses': True, 'crm': True},
            limits={'messages_per_month': 1000, 'leads': 500},
            stripe_price_id='price_basic123',
            stripe_product_id='prod_basic123'
        )
        return plan
    
    @pytest.fixture
    def pro_plan(self, db_session):
        """Create pro test plan."""
        plan = Plan.create(
            name='Pro Plan',
            price=Decimal('79.00'),
            billing_interval='month',
            features={'ai_responses': True, 'crm': True, 'kyb_monitoring': True},
            limits={'messages_per_month': 5000, 'leads': 2000},
            stripe_price_id='price_pro123',
            stripe_product_id='prod_pro123'
        )
        return plan
    
    @pytest.fixture
    def subscription(self, db_session, tenant, basic_plan):
        """Create test subscription."""
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            stripe_subscription_id='sub_test123',
            stripe_customer_id='cus_test123',
            status='active',
            current_period_start=datetime.utcnow().isoformat(),
            current_period_end=(datetime.utcnow() + timedelta(days=30)).isoformat()
        )
        return subscription
    
    @pytest.fixture
    def trial_subscription(self, db_session, tenant, basic_plan):
        """Create trial subscription."""
        trial_end = datetime.utcnow() + timedelta(days=3)
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            stripe_subscription_id='sub_trial123',
            stripe_customer_id='cus_test123',
            status='trialing',
            trial_start=datetime.utcnow().isoformat(),
            trial_end=trial_end.isoformat()
        )
        return subscription
    
    def test_create_plan_success(self, client, auth_headers):
        """Test successful plan creation."""
        plan_data = {
            'name': 'Test Plan',
            'price': 49.99,
            'billing_interval': 'month',
            'features': {'ai_responses': True},
            'limits': {'messages_per_month': 2000}
        }
        
        with patch('app.services.stripe_service.StripeService.create_plan') as mock_create:
            mock_plan = Plan(
                id=1,
                name='Test Plan',
                price=Decimal('49.99'),
                stripe_price_id='price_test123'
            )
            mock_create.return_value = mock_plan
            
            response = client.post(
                '/api/v1/billing/plans',
                json=plan_data,
                headers=auth_headers
            )
            
            assert response.status_code == 201
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['name'] == 'Test Plan'
            mock_create.assert_called_once()
    
    def test_create_plan_validation_error(self, client, auth_headers):
        """Test plan creation with validation errors."""
        plan_data = {
            'name': '',  # Empty name
            'price': -10  # Negative price
        }
        
        response = client.post(
            '/api/v1/billing/plans',
            json=plan_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'validation_errors' in data
    
    def test_update_plan_success(self, client, auth_headers, basic_plan):
        """Test successful plan update."""
        update_data = {
            'name': 'Updated Basic Plan',
            'features': {'ai_responses': True, 'advanced_analytics': True},
            'is_active': True
        }
        
        with patch('app.services.stripe_service.StripeService.update_plan') as mock_update:
            mock_update.return_value = basic_plan
            
            response = client.put(
                f'/api/v1/billing/plans/{basic_plan.id}',
                json=update_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            mock_update.assert_called_once_with(
                plan_id=basic_plan.id,
                name='Updated Basic Plan',
                features={'ai_responses': True, 'advanced_analytics': True},
                limits=None,
                is_active=True,
                metadata=None
            )
    
    def test_create_trial_subscription_success(self, client, auth_headers, basic_plan):
        """Test successful trial subscription creation."""
        trial_data = {
            'plan_id': basic_plan.id,
            'customer_email': 'test@example.com',
            'customer_name': 'Test User',
            'trial_days': 7
        }
        
        with patch('app.services.stripe_service.StripeService.create_customer') as mock_customer:
            with patch('app.services.stripe_service.StripeService.create_trial_subscription') as mock_trial:
                mock_customer.return_value = 'cus_test123'
                mock_subscription = Subscription(
                    id=1,
                    tenant_id=1,
                    plan_id=basic_plan.id,
                    status='trialing'
                )
                mock_trial.return_value = mock_subscription
                
                response = client.post(
                    '/api/v1/billing/subscriptions/trial',
                    json=trial_data,
                    headers=auth_headers
                )
                
                assert response.status_code == 201
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['status'] == 'trialing'
                mock_customer.assert_called_once()
                mock_trial.assert_called_once()
    
    def test_create_trial_subscription_validation_error(self, client, auth_headers):
        """Test trial subscription creation with validation errors."""
        trial_data = {
            'plan_id': 999,  # Non-existent plan
            'customer_email': 'invalid-email',  # Invalid email
            'trial_days': 50  # Too many trial days
        }
        
        response = client.post(
            '/api/v1/billing/subscriptions/trial',
            json=trial_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
    
    def test_upgrade_subscription_success(self, client, auth_headers, subscription, pro_plan):
        """Test successful subscription upgrade."""
        upgrade_data = {
            'new_plan_id': pro_plan.id,
            'prorate': True
        }
        
        with patch('app.services.stripe_service.StripeService.upgrade_subscription') as mock_upgrade:
            mock_upgrade.return_value = subscription
            
            response = client.post(
                f'/api/v1/billing/subscriptions/{subscription.id}/upgrade',
                json=upgrade_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            mock_upgrade.assert_called_once_with(
                subscription_id=subscription.id,
                new_plan_id=pro_plan.id,
                prorate=True
            )
    
    def test_upgrade_subscription_invalid_plan(self, client, auth_headers, subscription, basic_plan):
        """Test subscription upgrade with invalid plan (not higher tier)."""
        # Try to "upgrade" to the same plan
        upgrade_data = {
            'new_plan_id': basic_plan.id
        }
        
        response = client.post(
            f'/api/v1/billing/subscriptions/{subscription.id}/upgrade',
            json=upgrade_data,
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'higher tier' in data['error']['message']
    
    def test_downgrade_subscription_success(self, client, auth_headers, tenant, pro_plan, basic_plan):
        """Test successful subscription downgrade."""
        # Create subscription with pro plan
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=pro_plan.id,
            stripe_subscription_id='sub_pro123',
            status='active'
        )
        
        downgrade_data = {
            'new_plan_id': basic_plan.id,
            'at_period_end': True
        }
        
        with patch('app.services.stripe_service.StripeService.downgrade_subscription') as mock_downgrade:
            mock_downgrade.return_value = subscription
            
            response = client.post(
                f'/api/v1/billing/subscriptions/{subscription.id}/downgrade',
                json=downgrade_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            mock_downgrade.assert_called_once_with(
                subscription_id=subscription.id,
                new_plan_id=basic_plan.id,
                at_period_end=True
            )
    
    def test_expire_trial_success(self, client, auth_headers, trial_subscription):
        """Test successful trial expiration."""
        with patch('app.services.stripe_service.StripeService.handle_trial_expiration') as mock_expire:
            mock_expire.return_value = True
            
            response = client.post(
                f'/api/v1/billing/subscriptions/{trial_subscription.id}/trial/expire',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            mock_expire.assert_called_once_with(trial_subscription.id)
    
    def test_expire_trial_not_in_trial(self, client, auth_headers, subscription):
        """Test trial expiration for non-trial subscription."""
        response = client.post(
            f'/api/v1/billing/subscriptions/{subscription.id}/trial/expire',
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'not in trial' in data['error']['message']
    
    def test_handle_usage_overage_success(self, client, auth_headers, subscription):
        """Test successful usage overage handling."""
        overage_data = {
            'feature': 'messages_per_month',
            'current_usage': 1500  # Over the 1000 limit
        }
        
        with patch('app.services.stripe_service.StripeService.handle_usage_overage') as mock_overage:
            mock_overage.return_value = True
            
            response = client.post(
                f'/api/v1/billing/subscriptions/{subscription.id}/overage',
                json=overage_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['overage'] is True
            assert data['data']['overage_amount'] == 500
            mock_overage.assert_called_once()
    
    def test_handle_usage_overage_no_overage(self, client, auth_headers, subscription):
        """Test usage overage handling when under limit."""
        overage_data = {
            'feature': 'messages_per_month',
            'current_usage': 500  # Under the 1000 limit
        }
        
        with patch('app.services.stripe_service.StripeService.handle_usage_overage') as mock_overage:
            mock_overage.return_value = True
            
            response = client.post(
                f'/api/v1/billing/subscriptions/{subscription.id}/overage',
                json=overage_data,
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['overage'] is False
            assert data['data']['overage_amount'] == 0


class TestStripeServiceSubscriptionManagement:
    """Test StripeService subscription management methods."""
    
    @pytest.fixture
    def stripe_service(self):
        """Create StripeService instance."""
        return StripeService()
    
    @pytest.fixture
    def tenant(self, db_session):
        """Create test tenant."""
        return Tenant.create(name='Test Company', domain='test.com', slug='test-company')
    
    def test_create_plan_success(self, stripe_service):
        """Test successful plan creation in StripeService."""
        with patch('stripe.Product.create') as mock_product:
            with patch('stripe.Price.create') as mock_price:
                mock_product.return_value = MagicMock(id='prod_test123')
                mock_price.return_value = MagicMock(id='price_test123')
                
                plan = stripe_service.create_plan(
                    name='Test Plan',
                    price=Decimal('29.99'),
                    billing_interval='month',
                    features={'ai_responses': True},
                    limits={'messages_per_month': 1000}
                )
                
                assert plan.name == 'Test Plan'
                assert plan.price == Decimal('29.99')
                assert plan.stripe_price_id == 'price_test123'
                assert plan.stripe_product_id == 'prod_test123'
                mock_product.assert_called_once()
                mock_price.assert_called_once()
    
    def test_create_trial_subscription_success(self, stripe_service, tenant):
        """Test successful trial subscription creation."""
        plan = Plan.create(
            name='Test Plan',
            price=Decimal('29.99'),
            stripe_price_id='price_test123'
        )
        
        with patch('stripe.Subscription.create') as mock_create:
            mock_subscription = MagicMock()
            mock_subscription.id = 'sub_test123'
            mock_subscription.status = 'trialing'
            mock_subscription.current_period_start = int(datetime.utcnow().timestamp())
            mock_subscription.current_period_end = int((datetime.utcnow() + timedelta(days=30)).timestamp())
            mock_subscription.trial_start = int(datetime.utcnow().timestamp())
            mock_subscription.trial_end = int((datetime.utcnow() + timedelta(days=3)).timestamp())
            mock_subscription.created = int(datetime.utcnow().timestamp())
            mock_create.return_value = mock_subscription
            
            subscription = stripe_service.create_trial_subscription(
                tenant_id=tenant.id,
                customer_id='cus_test123',
                plan_id=plan.id,
                trial_days=3
            )
            
            assert subscription.status == 'trialing'
            assert subscription.stripe_subscription_id == 'sub_test123'
            assert subscription.trial_start is not None
            assert subscription.trial_end is not None
            mock_create.assert_called_once()
    
    def test_handle_trial_expiration_success(self, stripe_service, tenant):
        """Test successful trial expiration handling."""
        plan = Plan.create(
            name='Test Plan',
            price=Decimal('29.99'),
            limits={'messages_per_month': 1000, 'leads': 500}
        )
        
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            status='trialing',
            trial_end=(datetime.utcnow() - timedelta(hours=1)).isoformat()  # Expired
        )
        
        # Create entitlements
        Entitlement.create(
            tenant_id=tenant.id,
            subscription_id=subscription.id,
            feature='messages_per_month',
            limit_value=1000,
            used_value=0
        )
        
        with patch.object(stripe_service, '_send_trial_expiration_notification'):
            success = stripe_service.handle_trial_expiration(subscription.id)
            
            assert success is True
            
            # Check entitlements were updated to free tier limits
            entitlement = Entitlement.get_by_feature(subscription.id, 'messages_per_month')
            assert entitlement.limit_value == 100  # Free tier limit
    
    def test_upgrade_subscription_success(self, stripe_service, tenant):
        """Test successful subscription upgrade."""
        basic_plan = Plan.create(
            name='Basic Plan',
            price=Decimal('29.99'),
            stripe_price_id='price_basic123'
        )
        
        pro_plan = Plan.create(
            name='Pro Plan',
            price=Decimal('79.99'),
            stripe_price_id='price_pro123'
        )
        
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=basic_plan.id,
            stripe_subscription_id='sub_test123'
        )
        
        with patch('stripe.Subscription.retrieve') as mock_retrieve:
            with patch('stripe.Subscription.modify') as mock_modify:
                with patch.object(stripe_service, '_send_subscription_upgrade_notification'):
                    mock_stripe_sub = MagicMock()
                    mock_stripe_sub.items.data = [MagicMock(id='si_test123')]
                    mock_retrieve.return_value = mock_stripe_sub
                    
                    upgraded_subscription = stripe_service.upgrade_subscription(
                        subscription_id=subscription.id,
                        new_plan_id=pro_plan.id
                    )
                    
                    assert upgraded_subscription.plan_id == pro_plan.id
                    mock_modify.assert_called_once()
    
    def test_handle_usage_overage_success(self, stripe_service, tenant):
        """Test successful usage overage handling."""
        plan = Plan.create(
            name='Test Plan',
            price=Decimal('29.99')
        )
        
        subscription = Subscription.create(
            tenant_id=tenant.id,
            plan_id=plan.id,
            stripe_customer_id='cus_test123'
        )
        
        with patch('stripe.InvoiceItem.create') as mock_create_item:
            with patch.object(stripe_service, '_send_usage_overage_notification'):
                success = stripe_service.handle_usage_overage(
                    subscription_id=subscription.id,
                    feature='messages_per_month',
                    current_usage=1500,
                    limit=1000
                )
                
                assert success is True
                mock_create_item.assert_called_once()
                
                # Check usage event was recorded
                usage_events = UsageEvent.query.filter_by(
                    subscription_id=subscription.id,
                    event_type='messages_per_month_overage'
                ).all()
                assert len(usage_events) == 1
                assert usage_events[0].quantity == 500  # Overage amount
    
    def test_stripe_error_handling(self, stripe_service):
        """Test Stripe error handling in service methods."""
        with patch('stripe.Product.create') as mock_create:
            mock_create.side_effect = Exception('Stripe API error')
            
            with pytest.raises(StripeError):
                stripe_service.create_plan(
                    name='Test Plan',
                    price=Decimal('29.99')
                )