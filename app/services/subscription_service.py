"""Subscription management service for comprehensive subscription handling."""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional, Tuple
from flask import current_app
from sqlalchemy import and_, or_
from app import db
from app.models.billing import Plan, Subscription, UsageEvent, Entitlement, Invoice
from app.models.tenant import Tenant
from app.services.stripe_service import StripeService
from app.utils.exceptions import StripeError, ValidationError
import structlog

logger = structlog.get_logger()


class SubscriptionService:
    """Service for comprehensive subscription management."""
    
    def __init__(self):
        """Initialize subscription service."""
        self.stripe_service = StripeService()
    
    def create_plan(self, name: str, price: Decimal, billing_interval: str = 'month',
                   description: Optional[str] = None,
                   features: Optional[Dict[str, Any]] = None,
                   limits: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> Plan:
        """
        Create a new subscription plan with comprehensive validation.
        
        Args:
            name: Plan name
            price: Plan price
            billing_interval: Billing interval (month/year)
            description: Plan description
            features: Feature configuration
            limits: Usage limits
            metadata: Additional metadata
            
        Returns:
            Created Plan instance
            
        Raises:
            ValidationError: If validation fails
            StripeError: If Stripe integration fails
        """
        try:
            # Validate input
            self._validate_plan_data(name, price, billing_interval, features, limits)
            
            # Check for duplicate plan names
            existing_plan = Plan.query.filter_by(name=name, is_active=True).first()
            if existing_plan:
                raise ValidationError(f"Plan with name '{name}' already exists")
            
            # Create plan in Stripe first
            stripe_product, stripe_price = self.stripe_service.create_stripe_plan(
                name=name,
                price=price,
                billing_interval=billing_interval,
                description=description,
                metadata=metadata or {}
            )
            
            # Create local plan record
            plan = Plan.create(
                name=name,
                description=description,
                price=price,
                billing_interval=billing_interval,
                features=features or {},
                limits=limits or {},
                is_active=True,
                is_public=True,
                stripe_price_id=stripe_price.id,
                stripe_product_id=stripe_product.id,
                extra_data={
                    'created_by': 'subscription_service',
                    'stripe_data': {
                        'product_id': stripe_product.id,
                        'price_id': stripe_price.id,
                        'created': datetime.utcnow().isoformat()
                    },
                    **(metadata or {})
                }
            )
            
            logger.info("Plan created successfully", plan_id=plan.id, name=name, price=float(price))
            return plan
            
        except StripeError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error creating plan", error=str(e), name=name)
            raise ValidationError(f"Failed to create plan: {str(e)}")
    
    def create_trial_subscription(self, tenant_id: int, plan_id: int, 
                                customer_email: str, customer_name: Optional[str] = None,
                                trial_days: int = 3,
                                metadata: Optional[Dict[str, Any]] = None) -> Subscription:
        """
        Create a trial subscription with automatic transition handling.
        
        Args:
            tenant_id: Tenant ID
            plan_id: Plan ID
            customer_email: Customer email
            customer_name: Customer name
            trial_days: Trial period in days
            metadata: Additional metadata
            
        Returns:
            Created Subscription instance
            
        Raises:
            ValidationError: If validation fails
            StripeError: If Stripe integration fails
        """
        try:
            # Validate inputs
            if trial_days <= 0 or trial_days > 30:
                raise ValidationError("Trial days must be between 1 and 30")
            
            # Check if tenant already has an active subscription
            existing_subscription = Subscription.query.filter_by(
                tenant_id=tenant_id
            ).filter(
                Subscription.status.in_(['active', 'trialing'])
            ).first()
            
            if existing_subscription:
                raise ValidationError("Tenant already has an active subscription")
            
            # Get plan
            plan = Plan.get_by_id(plan_id)
            if not plan or not plan.is_active:
                raise ValidationError("Invalid or inactive plan")
            
            # Create or get Stripe customer
            customer_id = self.stripe_service.create_customer(
                tenant_id=tenant_id,
                email=customer_email,
                name=customer_name,
                metadata={
                    'tenant_id': str(tenant_id),
                    'trial_days': str(trial_days),
                    **(metadata or {})
                }
            )
            
            # Create trial subscription
            subscription = self.stripe_service.create_trial_subscription(
                tenant_id=tenant_id,
                customer_id=customer_id,
                plan_id=plan_id,
                trial_days=trial_days,
                metadata=metadata
            )
            
            # Schedule trial expiration check
            self._schedule_trial_expiration_check(subscription.id, trial_days)
            
            logger.info("Trial subscription created", 
                       subscription_id=subscription.id, 
                       tenant_id=tenant_id,
                       trial_days=trial_days)
            
            return subscription
            
        except StripeError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error creating trial subscription", 
                        error=str(e), 
                        tenant_id=tenant_id,
                        plan_id=plan_id)
            raise ValidationError(f"Failed to create trial subscription: {str(e)}")
    
    def handle_trial_expiration(self, subscription_id: int) -> Dict[str, Any]:
        """
        Handle trial expiration with automatic plan transitions.
        
        Args:
            subscription_id: Subscription ID
            
        Returns:
            Dict with transition results
            
        Raises:
            ValidationError: If subscription not found or invalid state
        """
        try:
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError(f"Subscription {subscription_id} not found")
            
            if not subscription.is_trial:
                raise ValidationError("Subscription is not in trial")
            
            # Check if trial has actually expired
            if subscription.trial_end:
                trial_end = datetime.fromisoformat(subscription.trial_end.replace('Z', '+00:00'))
                if datetime.utcnow() < trial_end:
                    return {'action': 'not_expired', 'trial_end': subscription.trial_end}
            
            # Check for payment method
            has_payment_method = self._check_payment_method(subscription)
            
            if has_payment_method:
                # Convert to paid subscription
                result = self._convert_trial_to_paid(subscription)
                logger.info("Trial converted to paid subscription", 
                           subscription_id=subscription_id,
                           tenant_id=subscription.tenant_id)
            else:
                # Handle no payment method
                result = self._handle_trial_without_payment(subscription)
                logger.info("Trial handled without payment method", 
                           subscription_id=subscription_id,
                           tenant_id=subscription.tenant_id,
                           action=result['action'])
            
            return result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error handling trial expiration", 
                        error=str(e), 
                        subscription_id=subscription_id)
            raise ValidationError(f"Failed to handle trial expiration: {str(e)}")
    
    def process_usage_overage(self, subscription_id: int, feature: str, 
                            current_usage: int) -> Dict[str, Any]:
        """
        Process usage overage and handle billing.
        
        Args:
            subscription_id: Subscription ID
            feature: Feature name
            current_usage: Current usage amount
            
        Returns:
            Dict with overage processing results
        """
        try:
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError(f"Subscription {subscription_id} not found")
            
            # Get entitlement for feature
            entitlement = Entitlement.get_by_feature(subscription_id, feature)
            if not entitlement:
                # No limit for this feature
                return {'action': 'no_limit', 'feature': feature}
            
            if entitlement.is_unlimited:
                return {'action': 'unlimited', 'feature': feature}
            
            # Check if over limit
            overage_amount = current_usage - entitlement.limit_value
            if overage_amount <= 0:
                return {'action': 'within_limit', 'feature': feature, 'usage': current_usage}
            
            # Calculate overage cost
            overage_cost = self._calculate_overage_cost(subscription, feature, overage_amount)
            
            if overage_cost > 0:
                # Create overage invoice
                invoice = self._create_overage_invoice(
                    subscription, 
                    feature, 
                    overage_amount, 
                    overage_cost
                )
                
                result = {
                    'action': 'overage_billed',
                    'feature': feature,
                    'overage_amount': overage_amount,
                    'overage_cost': float(overage_cost),
                    'invoice_id': invoice.id
                }
            else:
                # Free overage or grace period
                result = {
                    'action': 'overage_grace',
                    'feature': feature,
                    'overage_amount': overage_amount
                }
            
            # Update entitlement usage
            entitlement.used_value = current_usage
            entitlement.save()
            
            logger.info("Usage overage processed", 
                       subscription_id=subscription_id,
                       feature=feature,
                       overage_amount=overage_amount,
                       action=result['action'])
            
            return result
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error processing usage overage", 
                        error=str(e), 
                        subscription_id=subscription_id,
                        feature=feature)
            raise ValidationError(f"Failed to process usage overage: {str(e)}")
    
    def enforce_usage_quotas(self, tenant_id: int) -> Dict[str, Any]:
        """
        Enforce usage quotas for a tenant's subscriptions.
        
        Args:
            tenant_id: Tenant ID
            
        Returns:
            Dict with quota enforcement results
        """
        try:
            # Get active subscriptions for tenant
            subscriptions = Subscription.get_active_subscriptions(tenant_id)
            
            enforcement_results = []
            
            for subscription in subscriptions:
                # Get entitlements
                entitlements = Entitlement.query.filter_by(
                    subscription_id=subscription.id
                ).all()
                
                for entitlement in entitlements:
                    if entitlement.is_unlimited:
                        continue
                    
                    # Get current usage
                    current_usage = self._get_current_usage(
                        subscription.id, 
                        entitlement.feature
                    )
                    
                    # Check if over limit
                    if current_usage > entitlement.limit_value:
                        # Process overage
                        overage_result = self.process_usage_overage(
                            subscription.id,
                            entitlement.feature,
                            current_usage
                        )
                        enforcement_results.append({
                            'subscription_id': subscription.id,
                            'feature': entitlement.feature,
                            'current_usage': current_usage,
                            'limit': entitlement.limit_value,
                            'overage_result': overage_result
                        })
            
            return {
                'tenant_id': tenant_id,
                'enforced_count': len(enforcement_results),
                'results': enforcement_results,
                'processed_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error("Error enforcing usage quotas", 
                        error=str(e), 
                        tenant_id=tenant_id)
            raise ValidationError(f"Failed to enforce usage quotas: {str(e)}")
    
    def upgrade_subscription(self, subscription_id: int, new_plan_id: int,
                           prorate: bool = True) -> Dict[str, Any]:
        """
        Upgrade or downgrade a subscription to a new plan.
        
        Args:
            subscription_id: Subscription ID
            new_plan_id: New plan ID
            prorate: Whether to prorate the change
            
        Returns:
            Dict with upgrade results
        """
        try:
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError(f"Subscription {subscription_id} not found")
            
            new_plan = Plan.get_by_id(new_plan_id)
            if not new_plan or not new_plan.is_active:
                raise ValidationError("Invalid or inactive new plan")
            
            old_plan = subscription.plan
            
            # Update subscription in Stripe
            updated_subscription = self.stripe_service.update_subscription(
                subscription_id=subscription_id,
                plan_id=new_plan_id,
                metadata={'upgraded_at': datetime.utcnow().isoformat()}
            )
            
            # Update entitlements to new plan
            self._update_entitlements_to_plan(subscription, new_plan)
            
            result = {
                'subscription_id': subscription_id,
                'old_plan': old_plan.name if old_plan else None,
                'new_plan': new_plan.name,
                'prorate': prorate,
                'upgraded_at': datetime.utcnow().isoformat()
            }
            
            logger.info("Subscription upgraded", 
                       subscription_id=subscription_id,
                       old_plan=result['old_plan'],
                       new_plan=result['new_plan'])
            
            return result
            
        except StripeError:
            raise
        except ValidationError:
            raise
        except Exception as e:
            logger.error("Error upgrading subscription", 
                        error=str(e), 
                        subscription_id=subscription_id)
            raise ValidationError(f"Failed to upgrade subscription: {str(e)}")
    
    # Private helper methods
    
    def _validate_plan_data(self, name: str, price: Decimal, billing_interval: str,
                          features: Optional[Dict], limits: Optional[Dict]) -> None:
        """Validate plan creation data."""
        if not name or len(name.strip()) < 2:
            raise ValidationError("Plan name must be at least 2 characters")
        
        if price <= 0:
            raise ValidationError("Plan price must be positive")
        
        if billing_interval not in ['month', 'year']:
            raise ValidationError("Billing interval must be 'month' or 'year'")
        
        # Validate features structure
        if features:
            if not isinstance(features, dict):
                raise ValidationError("Features must be a dictionary")
        
        # Validate limits structure
        if limits:
            if not isinstance(limits, dict):
                raise ValidationError("Limits must be a dictionary")
            
            for limit_name, limit_value in limits.items():
                if not isinstance(limit_value, (int, float)) or (limit_value < -1):
                    raise ValidationError(f"Limit '{limit_name}' must be a non-negative number or -1 for unlimited")
    
    def _schedule_trial_expiration_check(self, subscription_id: int, trial_days: int) -> None:
        """Schedule trial expiration check."""
        try:
            from app.workers.billing import process_trial_expirations
            
            # Schedule task to run after trial period
            eta = datetime.utcnow() + timedelta(days=trial_days, hours=1)  # 1 hour buffer
            process_trial_expirations.apply_async(eta=eta)
            
        except Exception as e:
            logger.warning("Failed to schedule trial expiration check", 
                          error=str(e), 
                          subscription_id=subscription_id)
    
    def _check_payment_method(self, subscription: Subscription) -> bool:
        """Check if subscription has a valid payment method."""
        try:
            if not subscription.stripe_subscription_id:
                return False
            
            return self.stripe_service.has_valid_payment_method(
                subscription.stripe_subscription_id
            )
            
        except Exception as e:
            logger.warning("Error checking payment method", 
                          error=str(e), 
                          subscription_id=subscription.id)
            return False
    
    def _convert_trial_to_paid(self, subscription: Subscription) -> Dict[str, Any]:
        """Convert trial subscription to paid."""
        subscription.status = 'active'
        subscription.save()
        
        # Send conversion notification
        self._send_notification(
            subscription.tenant_id,
            'trial_converted',
            {'subscription_id': subscription.id}
        )
        
        return {
            'action': 'converted_to_paid',
            'subscription_id': subscription.id,
            'plan_name': subscription.plan.name if subscription.plan else None
        }
    
    def _handle_trial_without_payment(self, subscription: Subscription) -> Dict[str, Any]:
        """Handle trial expiration without payment method."""
        # Look for free plan
        free_plan = Plan.query.filter_by(name='Free', is_active=True).first()
        
        if free_plan:
            # Downgrade to free plan
            old_plan_name = subscription.plan.name if subscription.plan else None
            subscription.plan_id = free_plan.id
            subscription.status = 'active'
            subscription.save()
            
            # Update entitlements
            self._update_entitlements_to_plan(subscription, free_plan)
            
            # Send downgrade notification
            self._send_notification(
                subscription.tenant_id,
                'trial_downgraded',
                {
                    'subscription_id': subscription.id,
                    'old_plan': old_plan_name,
                    'new_plan': free_plan.name
                }
            )
            
            return {
                'action': 'downgraded_to_free',
                'subscription_id': subscription.id,
                'old_plan': old_plan_name,
                'new_plan': free_plan.name
            }
        else:
            # Suspend subscription
            subscription.status = 'past_due'
            subscription.save()
            
            # Send suspension notification
            self._send_notification(
                subscription.tenant_id,
                'trial_suspended',
                {'subscription_id': subscription.id}
            )
            
            return {
                'action': 'suspended',
                'subscription_id': subscription.id,
                'plan_name': subscription.plan.name if subscription.plan else None
            }
    
    def _calculate_overage_cost(self, subscription: Subscription, feature: str, 
                              overage_amount: int) -> Decimal:
        """Calculate cost for usage overage."""
        # Define overage rates per feature
        overage_rates = {
            'messages_per_month': Decimal('0.01'),  # $0.01 per message
            'knowledge_documents': Decimal('0.10'),  # $0.10 per document
            'leads': Decimal('0.05'),  # $0.05 per lead
            'users': Decimal('5.00'),  # $5.00 per user
        }
        
        rate = overage_rates.get(feature, Decimal('0.00'))
        return rate * overage_amount
    
    def _create_overage_invoice(self, subscription: Subscription, feature: str,
                              overage_amount: int, overage_cost: Decimal) -> Invoice:
        """Create invoice for usage overage."""
        description = f"Usage overage: {overage_amount} {feature.replace('_', ' ')}"
        
        return self.stripe_service.create_invoice(
            tenant_id=subscription.tenant_id,
            customer_id=subscription.stripe_customer_id,
            subscription_id=subscription.id,
            amount=overage_cost,
            description=description,
            metadata={
                'type': 'overage',
                'feature': feature,
                'overage_amount': str(overage_amount)
            }
        )
    
    def _get_current_usage(self, subscription_id: int, feature: str) -> int:
        """Get current usage for a feature."""
        # Get usage for current billing period
        subscription = Subscription.get_by_id(subscription_id)
        if not subscription or not subscription.current_period_start:
            return 0
        
        start_date = subscription.current_period_start
        end_date = datetime.utcnow().isoformat()
        
        return UsageEvent.get_total_usage(
            subscription_id=subscription_id,
            event_type=feature,
            start_date=start_date,
            end_date=end_date
        )
    
    def _update_entitlements_to_plan(self, subscription: Subscription, plan: Plan) -> None:
        """Update subscription entitlements to match new plan."""
        # Remove existing entitlements
        Entitlement.query.filter_by(subscription_id=subscription.id).delete()
        
        # Create new entitlements from plan
        Entitlement.create_from_plan(
            subscription.tenant_id,
            subscription.id,
            plan
        )
        
        db.session.commit()
    
    def _send_notification(self, tenant_id: int, notification_type: str, 
                         data: Dict[str, Any]) -> None:
        """Send notification (would be handled by notification worker)."""
        try:
            from app.workers.notifications import send_notification
            send_notification.delay(tenant_id, notification_type, data)
        except Exception as e:
            logger.warning("Failed to send notification", 
                          error=str(e), 
                          tenant_id=tenant_id,
                          notification_type=notification_type)