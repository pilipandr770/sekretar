"""Billing worker for Stripe integration and subscription management."""
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List, Optional
import stripe
from celery import current_task
from flask import current_app
from sqlalchemy import and_, or_
from app import db
from app.models.billing import Plan, Subscription, UsageEvent, Entitlement, Invoice
from app.models.tenant import Tenant
from app.services.stripe_service import StripeService
from app.utils.exceptions import StripeError, ValidationError
from app.workers.base import MonitoredWorker, create_task_decorator

logger = logging.getLogger(__name__)

# Create task decorator for billing queue
billing_task = create_task_decorator('billing', max_retries=3, default_retry_delay=300)


@billing_task
def sync_stripe_usage(tenant_id: int, subscription_id: int, 
                     start_date: str = None, end_date: str = None) -> Dict[str, Any]:
    """
    Synchronize usage data with Stripe for metering and billing.
    
    Args:
        tenant_id: Tenant ID
        subscription_id: Subscription ID
        start_date: Start date for sync (ISO format)
        end_date: End date for sync (ISO format)
    
    Returns:
        Dict with sync results
    """
    try:
        logger.info(f"Starting Stripe usage sync for subscription {subscription_id}")
        
        # Get subscription
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=tenant_id
        ).first()
        
        if not subscription:
            raise ValidationError(f"Subscription {subscription_id} not found")
        
        if not subscription.stripe_subscription_id:
            raise ValidationError("Subscription not linked to Stripe")
        
        # Set date range if not provided
        if not start_date:
            # Default to current billing period start
            start_date = subscription.current_period_start or (
                datetime.utcnow() - timedelta(days=30)
            ).isoformat()
        
        if not end_date:
            end_date = datetime.utcnow().isoformat()
        
        # Get usage events for the period
        usage_events = UsageEvent.query.filter(
            and_(
                UsageEvent.subscription_id == subscription_id,
                UsageEvent.timestamp >= start_date,
                UsageEvent.timestamp <= end_date
            )
        ).all()
        
        # Group usage by event type
        usage_summary = {}
        for event in usage_events:
            if event.event_type not in usage_summary:
                usage_summary[event.event_type] = 0
            usage_summary[event.event_type] += event.quantity
        
        # Sync with Stripe (if using metered billing)
        stripe_results = {}
        if subscription.plan and subscription.plan.stripe_price_id:
            try:
                stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                
                # Report usage to Stripe for metered items
                for event_type, quantity in usage_summary.items():
                    if event_type in ['messages_sent', 'documents_processed', 'api_calls']:
                        try:
                            usage_record = stripe.SubscriptionItem.create_usage_record(
                                subscription.stripe_subscription_id,
                                quantity=quantity,
                                timestamp=int(datetime.fromisoformat(end_date).timestamp()),
                                action='set'  # Set total usage for the period
                            )
                            stripe_results[event_type] = {
                                'quantity': quantity,
                                'stripe_id': usage_record.id,
                                'timestamp': usage_record.timestamp
                            }
                        except stripe.error.StripeError as e:
                            logger.warning(f"Failed to sync {event_type} usage to Stripe: {e}")
                            stripe_results[event_type] = {'error': str(e)}
                            
            except Exception as e:
                logger.error(f"Stripe usage sync error: {e}")
                stripe_results['error'] = str(e)
        
        # Update entitlements based on usage
        _update_entitlements_from_usage(subscription, usage_summary)
        
        result = {
            'subscription_id': subscription_id,
            'tenant_id': tenant_id,
            'period': {'start': start_date, 'end': end_date},
            'usage_summary': usage_summary,
            'stripe_results': stripe_results,
            'synced_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed Stripe usage sync for subscription {subscription_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in sync_stripe_usage: {e}")
        raise


@billing_task
def enforce_subscription_quotas(tenant_id: int, subscription_id: int = None) -> Dict[str, Any]:
    """
    Enforce subscription quotas and limits.
    
    Args:
        tenant_id: Tenant ID
        subscription_id: Optional specific subscription ID
    
    Returns:
        Dict with enforcement results
    """
    try:
        logger.info(f"Starting quota enforcement for tenant {tenant_id}")
        
        # Get subscriptions to check
        if subscription_id:
            subscriptions = Subscription.query.filter_by(
                id=subscription_id,
                tenant_id=tenant_id
            ).all()
        else:
            subscriptions = Subscription.get_active_subscriptions(tenant_id)
        
        enforcement_results = []
        
        for subscription in subscriptions:
            if not subscription.is_active:
                continue
                
            # Get current usage for this billing period
            period_start = subscription.current_period_start or (
                datetime.utcnow() - timedelta(days=30)
            ).isoformat()
            
            current_usage = _calculate_current_usage(subscription, period_start)
            
            # Check each limit
            quota_violations = []
            for limit_name, limit_value in (subscription.plan.limits or {}).items():
                if limit_value == -1:  # Unlimited
                    continue
                    
                current_value = current_usage.get(limit_name, 0)
                
                # Get or create entitlement
                entitlement = Entitlement.get_by_feature(subscription.id, limit_name)
                if not entitlement:
                    entitlement = Entitlement.create(
                        tenant_id=tenant_id,
                        subscription_id=subscription.id,
                        feature=limit_name,
                        limit_value=limit_value,
                        used_value=current_value,
                        reset_frequency='monthly' if limit_name.endswith('_per_month') else 'never'
                    )
                else:
                    entitlement.used_value = current_value
                    entitlement.save()
                
                # Check for violations
                if current_value > limit_value:
                    quota_violations.append({
                        'feature': limit_name,
                        'limit': limit_value,
                        'current_usage': current_value,
                        'overage': current_value - limit_value,
                        'percentage': (current_value / limit_value) * 100
                    })
            
            # Handle quota violations
            actions_taken = []
            if quota_violations:
                actions_taken = _handle_quota_violations(subscription, quota_violations)
            
            enforcement_results.append({
                'subscription_id': subscription.id,
                'plan_name': subscription.plan.name if subscription.plan else None,
                'current_usage': current_usage,
                'quota_violations': quota_violations,
                'actions_taken': actions_taken
            })
        
        result = {
            'tenant_id': tenant_id,
            'subscriptions_checked': len(subscriptions),
            'enforcement_results': enforcement_results,
            'enforced_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed quota enforcement for tenant {tenant_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in enforce_subscription_quotas: {e}")
        raise


@billing_task
def process_trial_expirations(self) -> Dict[str, Any]:
    """
    Process trial expirations and handle transitions.
    
    Returns:
        Dict with processing results
    """
    try:
        logger.info("Starting trial expiration processing")
        
        # Find subscriptions with expired trials
        now = datetime.utcnow().isoformat()
        expired_trials = Subscription.query.filter(
            and_(
                Subscription.status == 'trialing',
                Subscription.trial_end <= now,
                Subscription.deleted_at.is_(None)
            )
        ).all()
        
        processing_results = []
        
        for subscription in expired_trials:
            try:
                # Check if there's a valid payment method in Stripe
                has_payment_method = False
                if subscription.stripe_subscription_id:
                    try:
                        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                        
                        # Check if customer has a default payment method
                        customer = stripe.Customer.retrieve(stripe_sub.customer)
                        has_payment_method = bool(customer.default_source or 
                                                customer.invoice_settings.default_payment_method)
                        
                    except stripe.error.StripeError as e:
                        logger.warning(f"Error checking payment method for subscription {subscription.id}: {e}")
                
                if has_payment_method:
                    # Transition to active subscription
                    subscription.status = 'active'
                    subscription.save()
                    
                    # Send welcome email (would be handled by notification worker)
                    _schedule_notification(
                        subscription.tenant_id,
                        'trial_converted',
                        {'subscription_id': subscription.id}
                    )
                    
                    processing_results.append({
                        'subscription_id': subscription.id,
                        'tenant_id': subscription.tenant_id,
                        'action': 'converted_to_active',
                        'plan_name': subscription.plan.name if subscription.plan else None
                    })
                    
                else:
                    # No payment method - downgrade to free plan or suspend
                    free_plan = Plan.query.filter_by(name='Free', is_active=True).first()
                    
                    if free_plan:
                        # Downgrade to free plan
                        old_plan = subscription.plan.name if subscription.plan else None
                        subscription.plan_id = free_plan.id
                        subscription.status = 'active'
                        subscription.save()
                        
                        # Reset entitlements to free plan limits
                        _reset_entitlements_to_plan(subscription, free_plan)
                        
                        processing_results.append({
                            'subscription_id': subscription.id,
                            'tenant_id': subscription.tenant_id,
                            'action': 'downgraded_to_free',
                            'old_plan': old_plan,
                            'new_plan': free_plan.name
                        })
                        
                    else:
                        # Suspend subscription
                        subscription.status = 'past_due'
                        subscription.save()
                        
                        processing_results.append({
                            'subscription_id': subscription.id,
                            'tenant_id': subscription.tenant_id,
                            'action': 'suspended',
                            'plan_name': subscription.plan.name if subscription.plan else None
                        })
                    
                    # Send trial expired notification
                    _schedule_notification(
                        subscription.tenant_id,
                        'trial_expired',
                        {'subscription_id': subscription.id, 'has_payment_method': has_payment_method}
                    )
                
            except Exception as e:
                logger.error(f"Error processing trial expiration for subscription {subscription.id}: {e}")
                processing_results.append({
                    'subscription_id': subscription.id,
                    'tenant_id': subscription.tenant_id,
                    'action': 'error',
                    'error': str(e)
                })
        
        result = {
            'processed_count': len(expired_trials),
            'processing_results': processing_results,
            'processed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed trial expiration processing: {len(expired_trials)} subscriptions")
        return result
        
    except Exception as e:
        logger.error(f"Error in process_trial_expirations: {e}")
        raise


@billing_task
def handle_plan_upgrades(tenant_id: int, subscription_id: int, 
                        new_plan_id: int, prorate: bool = True) -> Dict[str, Any]:
    """
    Handle subscription plan upgrades/downgrades.
    
    Args:
        tenant_id: Tenant ID
        subscription_id: Subscription ID
        new_plan_id: New plan ID
        prorate: Whether to prorate the change
    
    Returns:
        Dict with upgrade results
    """
    try:
        logger.info(f"Starting plan upgrade for subscription {subscription_id}")
        
        # Get subscription and new plan
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=tenant_id
        ).first()
        
        if not subscription:
            raise ValidationError(f"Subscription {subscription_id} not found")
        
        new_plan = Plan.get_by_id(new_plan_id)
        if not new_plan or not new_plan.is_active:
            raise ValidationError(f"Plan {new_plan_id} not found or inactive")
        
        old_plan = subscription.plan
        
        # Update subscription in Stripe if linked
        stripe_result = None
        if subscription.stripe_subscription_id and new_plan.stripe_price_id:
            try:
                stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                
                # Update Stripe subscription
                stripe_sub = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        'id': subscription.stripe_subscription_id,  # This would need the item ID
                        'price': new_plan.stripe_price_id,
                    }],
                    proration_behavior='create_prorations' if prorate else 'none'
                )
                
                stripe_result = {
                    'stripe_subscription_id': stripe_sub.id,
                    'status': stripe_sub.status,
                    'current_period_start': datetime.fromtimestamp(
                        stripe_sub.current_period_start
                    ).isoformat(),
                    'current_period_end': datetime.fromtimestamp(
                        stripe_sub.current_period_end
                    ).isoformat()
                }
                
                # Update local subscription with Stripe data
                subscription.current_period_start = stripe_result['current_period_start']
                subscription.current_period_end = stripe_result['current_period_end']
                
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error during plan upgrade: {e}")
                raise StripeError(f"Failed to update Stripe subscription: {e}")
        
        # Update local subscription
        subscription.plan_id = new_plan_id
        subscription.save()
        
        # Update entitlements for new plan
        _reset_entitlements_to_plan(subscription, new_plan)
        
        # Create usage event for plan change
        UsageEvent.record_usage(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            event_type='plan_change',
            quantity=1,
            old_plan_id=old_plan.id if old_plan else None,
            new_plan_id=new_plan_id,
            prorate=prorate
        )
        
        # Send notification
        _schedule_notification(
            tenant_id,
            'plan_upgraded' if new_plan.price > (old_plan.price if old_plan else 0) else 'plan_downgraded',
            {
                'subscription_id': subscription_id,
                'old_plan': old_plan.name if old_plan else None,
                'new_plan': new_plan.name,
                'prorate': prorate
            }
        )
        
        result = {
            'subscription_id': subscription_id,
            'tenant_id': tenant_id,
            'old_plan': old_plan.name if old_plan else None,
            'new_plan': new_plan.name,
            'prorate': prorate,
            'stripe_result': stripe_result,
            'upgraded_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed plan upgrade for subscription {subscription_id}")
        return result
        
    except Exception as e:
        logger.error(f"Error in handle_plan_upgrades: {e}")
        raise


@billing_task
def sync_subscription_status(subscription_id: int = None, tenant_id: int = None) -> Dict[str, Any]:
    """
    Sync subscription status with Stripe.
    
    Args:
        subscription_id: Optional specific subscription ID
        tenant_id: Optional tenant ID to sync all subscriptions
    
    Returns:
        Dict with sync results
    """
    try:
        logger.info("Starting subscription status sync")
        
        # Get subscriptions to sync
        if subscription_id:
            subscriptions = [Subscription.get_by_id(subscription_id)]
        elif tenant_id:
            subscriptions = Subscription.query.filter_by(tenant_id=tenant_id).all()
        else:
            # Sync all active subscriptions
            subscriptions = Subscription.query.filter(
                Subscription.stripe_subscription_id.isnot(None)
            ).all()
        
        sync_results = []
        stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        
        for subscription in subscriptions:
            if not subscription or not subscription.stripe_subscription_id:
                continue
                
            try:
                # Get current status from Stripe
                stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                
                # Check if status changed
                status_changed = subscription.status != stripe_sub.status
                
                # Update local subscription
                subscription.status = stripe_sub.status
                subscription.current_period_start = datetime.fromtimestamp(
                    stripe_sub.current_period_start
                ).isoformat()
                subscription.current_period_end = datetime.fromtimestamp(
                    stripe_sub.current_period_end
                ).isoformat()
                
                if stripe_sub.trial_end:
                    subscription.trial_end = datetime.fromtimestamp(
                        stripe_sub.trial_end
                    ).isoformat()
                
                if stripe_sub.canceled_at:
                    subscription.canceled_at = datetime.fromtimestamp(
                        stripe_sub.canceled_at
                    ).isoformat()
                
                subscription.cancel_at_period_end = stripe_sub.cancel_at_period_end
                subscription.save()
                
                sync_results.append({
                    'subscription_id': subscription.id,
                    'tenant_id': subscription.tenant_id,
                    'status': stripe_sub.status,
                    'status_changed': status_changed,
                    'current_period_end': subscription.current_period_end
                })
                
                # Handle status-specific actions
                if status_changed:
                    _handle_subscription_status_change(subscription, stripe_sub.status)
                
            except stripe.error.StripeError as e:
                logger.error(f"Stripe error syncing subscription {subscription.id}: {e}")
                sync_results.append({
                    'subscription_id': subscription.id,
                    'tenant_id': subscription.tenant_id,
                    'error': str(e)
                })
        
        result = {
            'synced_count': len([r for r in sync_results if 'error' not in r]),
            'error_count': len([r for r in sync_results if 'error' in r]),
            'sync_results': sync_results,
            'synced_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed subscription status sync: {result['synced_count']} synced, {result['error_count']} errors")
        return result
        
    except Exception as e:
        logger.error(f"Error in sync_subscription_status: {e}")
        raise


@billing_task
def process_failed_payments(self) -> Dict[str, Any]:
    """
    Process failed payments and handle dunning.
    
    Returns:
        Dict with processing results
    """
    try:
        logger.info("Starting failed payment processing")
        
        # Find subscriptions with failed payments
        failed_subscriptions = Subscription.query.filter(
            Subscription.status.in_(['past_due', 'unpaid'])
        ).all()
        
        processing_results = []
        
        for subscription in failed_subscriptions:
            try:
                # Get latest invoice status from Stripe
                if subscription.stripe_subscription_id:
                    stripe.api_key = current_app.config.get('STRIPE_SECRET_KEY')
                    stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                    
                    # Get latest invoice
                    invoices = stripe.Invoice.list(
                        subscription=subscription.stripe_subscription_id,
                        limit=1
                    )
                    
                    if invoices.data:
                        latest_invoice = invoices.data[0]
                        
                        # Sync invoice status
                        local_invoice = Invoice.get_by_stripe_id(latest_invoice.id)
                        if local_invoice:
                            local_invoice.status = latest_invoice.status
                            local_invoice.save()
                        
                        # Handle based on invoice status
                        if latest_invoice.status == 'paid':
                            # Payment succeeded, reactivate subscription
                            subscription.status = 'active'
                            subscription.save()
                            
                            processing_results.append({
                                'subscription_id': subscription.id,
                                'tenant_id': subscription.tenant_id,
                                'action': 'reactivated',
                                'invoice_id': latest_invoice.id
                            })
                            
                        elif latest_invoice.status == 'open':
                            # Still unpaid, send reminder
                            days_overdue = _calculate_days_overdue(latest_invoice)
                            
                            if days_overdue >= 7:  # 7 days overdue
                                # Send final notice or suspend
                                if days_overdue >= 14:  # 14 days overdue
                                    subscription.status = 'canceled'
                                    subscription.canceled_at = datetime.utcnow().isoformat()
                                    subscription.save()
                                    
                                    _schedule_notification(
                                        subscription.tenant_id,
                                        'subscription_canceled_nonpayment',
                                        {'subscription_id': subscription.id}
                                    )
                                    
                                    processing_results.append({
                                        'subscription_id': subscription.id,
                                        'tenant_id': subscription.tenant_id,
                                        'action': 'canceled_nonpayment',
                                        'days_overdue': days_overdue
                                    })
                                else:
                                    _schedule_notification(
                                        subscription.tenant_id,
                                        'payment_final_notice',
                                        {
                                            'subscription_id': subscription.id,
                                            'days_overdue': days_overdue
                                        }
                                    )
                                    
                                    processing_results.append({
                                        'subscription_id': subscription.id,
                                        'tenant_id': subscription.tenant_id,
                                        'action': 'final_notice_sent',
                                        'days_overdue': days_overdue
                                    })
                            else:
                                # Send payment reminder
                                _schedule_notification(
                                    subscription.tenant_id,
                                    'payment_reminder',
                                    {
                                        'subscription_id': subscription.id,
                                        'days_overdue': days_overdue
                                    }
                                )
                                
                                processing_results.append({
                                    'subscription_id': subscription.id,
                                    'tenant_id': subscription.tenant_id,
                                    'action': 'reminder_sent',
                                    'days_overdue': days_overdue
                                })
                
            except Exception as e:
                logger.error(f"Error processing failed payment for subscription {subscription.id}: {e}")
                processing_results.append({
                    'subscription_id': subscription.id,
                    'tenant_id': subscription.tenant_id,
                    'action': 'error',
                    'error': str(e)
                })
        
        result = {
            'processed_count': len(failed_subscriptions),
            'processing_results': processing_results,
            'processed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed failed payment processing: {len(failed_subscriptions)} subscriptions")
        return result
        
    except Exception as e:
        logger.error(f"Error in process_failed_payments: {e}")
        raise


# Helper functions

def _update_entitlements_from_usage(subscription: Subscription, usage_summary: Dict[str, int]):
    """Update entitlements based on current usage."""
    for feature, usage_count in usage_summary.items():
        entitlement = Entitlement.get_by_feature(subscription.id, feature)
        if entitlement:
            entitlement.used_value = usage_count
            entitlement.save()


def _calculate_current_usage(subscription: Subscription, period_start: str) -> Dict[str, int]:
    """Calculate current usage for a subscription."""
    usage_events = UsageEvent.query.filter(
        and_(
            UsageEvent.subscription_id == subscription.id,
            UsageEvent.timestamp >= period_start
        )
    ).all()
    
    usage_summary = {}
    for event in usage_events:
        if event.event_type not in usage_summary:
            usage_summary[event.event_type] = 0
        usage_summary[event.event_type] += event.quantity
    
    return usage_summary


def _handle_quota_violations(subscription: Subscription, violations: List[Dict]) -> List[str]:
    """Handle quota violations."""
    actions = []
    
    for violation in violations:
        feature = violation['feature']
        overage = violation['overage']
        
        # Log violation
        logger.warning(
            f"Quota violation for subscription {subscription.id}: "
            f"{feature} usage {violation['current_usage']} exceeds limit {violation['limit']}"
        )
        
        # Record overage usage event
        UsageEvent.record_usage(
            tenant_id=subscription.tenant_id,
            subscription_id=subscription.id,
            event_type=f"{feature}_overage",
            quantity=overage
        )
        
        # Send notification
        _schedule_notification(
            subscription.tenant_id,
            'quota_exceeded',
            {
                'subscription_id': subscription.id,
                'feature': feature,
                'limit': violation['limit'],
                'current_usage': violation['current_usage'],
                'overage': overage
            }
        )
        
        actions.append(f"Recorded {feature} overage: {overage}")
    
    return actions


def _reset_entitlements_to_plan(subscription: Subscription, plan: Plan):
    """Reset entitlements to match plan limits."""
    # Remove existing entitlements
    Entitlement.query.filter_by(subscription_id=subscription.id).delete()
    
    # Create new entitlements from plan
    if plan.limits:
        for feature, limit in plan.limits.items():
            Entitlement.create(
                tenant_id=subscription.tenant_id,
                subscription_id=subscription.id,
                feature=feature,
                limit_value=limit,
                used_value=0,
                reset_frequency='monthly' if feature.endswith('_per_month') else 'never'
            )
    
    db.session.commit()


def _handle_subscription_status_change(subscription: Subscription, new_status: str):
    """Handle subscription status changes."""
    if new_status == 'canceled':
        _schedule_notification(
            subscription.tenant_id,
            'subscription_canceled',
            {'subscription_id': subscription.id}
        )
    elif new_status == 'active' and subscription.status in ['past_due', 'unpaid']:
        _schedule_notification(
            subscription.tenant_id,
            'subscription_reactivated',
            {'subscription_id': subscription.id}
        )


def _calculate_days_overdue(stripe_invoice) -> int:
    """Calculate days overdue for an invoice."""
    if not stripe_invoice.get('due_date'):
        return 0
    
    due_date = datetime.fromtimestamp(stripe_invoice['due_date'])
    return max(0, (datetime.utcnow() - due_date).days)


def _schedule_notification(tenant_id: int, notification_type: str, data: Dict[str, Any]):
    """Schedule a notification to be sent."""
    try:
        # Import notification worker if available (task 7.4)
        try:
            from app.workers.notifications import send_notification
            send_notification.apply_async(
                args=[tenant_id, notification_type, data],
                queue='notifications'
            )
        except ImportError:
            # Notification worker not implemented yet, log for now
            logger.info(f"Notification scheduled for tenant {tenant_id}: {notification_type} - {data}")
    except Exception as e:
        logger.error(f"Failed to schedule notification: {e}")


# Periodic tasks (would be scheduled via Celery Beat)

@billing_task
def daily_billing_sync(self) -> Dict[str, Any]:
    """Daily billing synchronization task."""
    try:
        logger.info("Starting daily billing sync")
        
        results = {
            'subscription_sync': sync_subscription_status.delay().get(),
            'trial_processing': process_trial_expirations.delay().get(),
            'failed_payments': process_failed_payments.delay().get(),
            'synced_at': datetime.utcnow().isoformat()
        }
        
        logger.info("Completed daily billing sync")
        return results
        
    except Exception as e:
        logger.error(f"Error in daily_billing_sync: {e}")
        raise


@billing_task
def hourly_quota_enforcement(self) -> Dict[str, Any]:
    """Hourly quota enforcement task."""
    try:
        logger.info("Starting hourly quota enforcement")
        
        # Get all active subscriptions
        active_subscriptions = Subscription.get_active_subscriptions()
        
        results = []
        for subscription in active_subscriptions:
            try:
                result = enforce_subscription_quotas.delay(
                    subscription.tenant_id,
                    subscription.id
                ).get()
                results.append(result)
            except Exception as e:
                logger.error(f"Error enforcing quotas for subscription {subscription.id}: {e}")
        
        summary = {
            'subscriptions_processed': len(results),
            'total_violations': sum(
                len(r.get('enforcement_results', [{}])[0].get('quota_violations', []))
                for r in results
            ),
            'processed_at': datetime.utcnow().isoformat()
        }
        
        logger.info(f"Completed hourly quota enforcement: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Error in hourly_quota_enforcement: {e}")
        raise