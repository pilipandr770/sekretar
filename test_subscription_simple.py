#!/usr/bin/env python3
"""Simple test for subscription management functionality."""

import sys
import os
sys.path.insert(0, os.path.abspath('.'))

from decimal import Decimal
from app import create_app
from app.services.subscription_service import SubscriptionService
from app.models.billing import Plan, Subscription, Entitlement
from app.models.tenant import Tenant

def test_subscription_service():
    """Test subscription service functionality."""
    print("Testing SubscriptionService...")
    
    app = create_app('testing')
    with app.app_context():
        # Test plan validation
        service = SubscriptionService()
        
        try:
            # Test plan data validation
            service._validate_plan_data(
                name="Test Plan",
                price=Decimal('29.99'),
                billing_interval='month',
                features={'ai_responses': True},
                limits={'messages_per_month': 1000}
            )
            print("✓ Plan validation works")
        except Exception as e:
            print(f"✗ Plan validation failed: {e}")
        
        try:
            # Test overage cost calculation
            subscription = Subscription()
            cost = service._calculate_overage_cost(subscription, 'messages_per_month', 100)
            print(f"✓ Overage cost calculation works: ${cost}")
        except Exception as e:
            print(f"✗ Overage cost calculation failed: {e}")
        
        try:
            # Test usage quota enforcement logic
            result = service.enforce_usage_quotas(1)  # Test with tenant_id=1
            print(f"✓ Usage quota enforcement works: {result['enforced_count']} enforcements")
        except Exception as e:
            print(f"✗ Usage quota enforcement failed: {e}")
    
    print("SubscriptionService tests completed!")

if __name__ == '__main__':
    test_subscription_service()