"""Stripe integration service for invoice management."""
import stripe
from typing import Optional, Dict, Any, List, Tuple
from decimal import Decimal
from datetime import datetime
from flask import current_app
from app.models.billing import Invoice, Subscription
from app.models.tenant import Tenant
from app.utils.exceptions import StripeError, ValidationError


class StripeService:
    """Service for Stripe invoice operations."""
    
    def __init__(self):
        """Initialize Stripe service."""
        self.api_key = current_app.config.get('STRIPE_SECRET_KEY')
        if self.api_key:
            stripe.api_key = self.api_key
    
    def create_invoice(self, tenant_id: int, customer_id: str, 
                      subscription_id: Optional[int] = None,
                      amount: Optional[Decimal] = None,
                      currency: str = 'USD',
                      description: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Invoice:
        """Create a new invoice in Stripe and local database."""
        try:
            # Prepare invoice data
            invoice_data = {
                'customer': customer_id,
                'currency': currency.lower(),
                'metadata': metadata or {}
            }
            
            # Add subscription if provided
            if subscription_id:
                subscription = Subscription.get_by_id(subscription_id)
                if subscription and subscription.stripe_subscription_id:
                    invoice_data['subscription'] = subscription.stripe_subscription_id
            
            # Add description if provided
            if description:
                invoice_data['description'] = description
            
            # Create invoice in Stripe
            stripe_invoice = stripe.Invoice.create(**invoice_data)
            
            # Add invoice items if amount is specified (for one-time charges)
            if amount and not subscription_id:
                stripe.InvoiceItem.create(
                    customer=customer_id,
                    amount=int(amount * 100),  # Convert to cents
                    currency=currency.lower(),
                    description=description or 'One-time charge',
                    invoice=stripe_invoice.id
                )
                
                # Refresh invoice to get updated total
                stripe_invoice = stripe.Invoice.retrieve(stripe_invoice.id)
            
            # Create local invoice record
            invoice = Invoice.create(
                tenant_id=tenant_id,
                subscription_id=subscription_id,
                stripe_invoice_id=stripe_invoice.id,
                stripe_payment_intent_id=stripe_invoice.payment_intent,
                invoice_number=stripe_invoice.number,
                amount_total=Decimal(str(stripe_invoice.total / 100)),
                amount_paid=Decimal(str(stripe_invoice.amount_paid / 100)),
                currency=stripe_invoice.currency.upper(),
                status=stripe_invoice.status,
                invoice_date=datetime.fromtimestamp(stripe_invoice.created).isoformat(),
                due_date=datetime.fromtimestamp(stripe_invoice.due_date).isoformat() if stripe_invoice.due_date else None,
                hosted_invoice_url=stripe_invoice.hosted_invoice_url,
                invoice_pdf_url=stripe_invoice.invoice_pdf,
                extra_data={
                    'stripe_data': {
                        'id': stripe_invoice.id,
                        'number': stripe_invoice.number,
                        'created': stripe_invoice.created,
                        'lines': [
                            {
                                'description': line.description,
                                'amount': line.amount,
                                'quantity': line.quantity
                            } for line in stripe_invoice.lines.data
                        ]
                    }
                }
            )
            
            return invoice
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating invoice: {str(e)}")
            raise StripeError(f"Failed to create invoice: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error creating invoice: {str(e)}")
            raise
    
    def finalize_invoice(self, invoice_id: int) -> Invoice:
        """Finalize a draft invoice."""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                raise ValidationError("Invoice not found")
            
            if not invoice.stripe_invoice_id:
                raise ValidationError("Invoice not linked to Stripe")
            
            # Finalize in Stripe
            stripe_invoice = stripe.Invoice.finalize_invoice(invoice.stripe_invoice_id)
            
            # Update local record
            invoice.status = stripe_invoice.status
            invoice.invoice_number = stripe_invoice.number
            invoice.hosted_invoice_url = stripe_invoice.hosted_invoice_url
            invoice.invoice_pdf_url = stripe_invoice.invoice_pdf
            invoice.save()
            
            return invoice
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error finalizing invoice: {str(e)}")
            raise StripeError(f"Failed to finalize invoice: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error finalizing invoice: {str(e)}")
            raise
    
    def send_invoice(self, invoice_id: int) -> Invoice:
        """Send invoice to customer."""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                raise ValidationError("Invoice not found")
            
            if not invoice.stripe_invoice_id:
                raise ValidationError("Invoice not linked to Stripe")
            
            # Send invoice in Stripe
            stripe_invoice = stripe.Invoice.send_invoice(invoice.stripe_invoice_id)
            
            # Update local record
            invoice.status = stripe_invoice.status
            invoice.save()
            
            return invoice
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error sending invoice: {str(e)}")
            raise StripeError(f"Failed to send invoice: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error sending invoice: {str(e)}")
            raise
    
    def void_invoice(self, invoice_id: int) -> Invoice:
        """Void an invoice."""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                raise ValidationError("Invoice not found")
            
            if not invoice.stripe_invoice_id:
                raise ValidationError("Invoice not linked to Stripe")
            
            # Void invoice in Stripe
            stripe_invoice = stripe.Invoice.void_invoice(invoice.stripe_invoice_id)
            
            # Update local record
            invoice.status = stripe_invoice.status
            invoice.save()
            
            return invoice
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error voiding invoice: {str(e)}")
            raise StripeError(f"Failed to void invoice: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error voiding invoice: {str(e)}")
            raise
    
    def get_invoice_status(self, invoice_id: int) -> Dict[str, Any]:
        """Get current invoice status from Stripe."""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                raise ValidationError("Invoice not found")
            
            if not invoice.stripe_invoice_id:
                raise ValidationError("Invoice not linked to Stripe")
            
            # Get invoice from Stripe
            stripe_invoice = stripe.Invoice.retrieve(invoice.stripe_invoice_id)
            
            # Update local record if status changed
            if invoice.status != stripe_invoice.status:
                invoice.status = stripe_invoice.status
                invoice.amount_paid = Decimal(str(stripe_invoice.amount_paid / 100))
                if stripe_invoice.status == 'paid' and stripe_invoice.status_transitions.paid_at:
                    invoice.paid_at = datetime.fromtimestamp(
                        stripe_invoice.status_transitions.paid_at
                    ).isoformat()
                invoice.save()
            
            return {
                'id': invoice.id,
                'stripe_id': stripe_invoice.id,
                'status': stripe_invoice.status,
                'amount_total': float(stripe_invoice.total / 100),
                'amount_paid': float(stripe_invoice.amount_paid / 100),
                'amount_due': float(stripe_invoice.amount_due / 100),
                'currency': stripe_invoice.currency.upper(),
                'paid_at': datetime.fromtimestamp(
                    stripe_invoice.status_transitions.paid_at
                ).isoformat() if stripe_invoice.status_transitions.paid_at else None,
                'hosted_invoice_url': stripe_invoice.hosted_invoice_url,
                'invoice_pdf': stripe_invoice.invoice_pdf
            }
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error getting invoice status: {str(e)}")
            raise StripeError(f"Failed to get invoice status: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error getting invoice status: {str(e)}")
            raise
    
    def sync_invoice_from_stripe(self, stripe_invoice_id: str) -> Invoice:
        """Sync invoice data from Stripe."""
        try:
            # Get invoice from Stripe
            stripe_invoice = stripe.Invoice.retrieve(stripe_invoice_id)
            
            # Find or create local invoice
            invoice = Invoice.get_by_stripe_id(stripe_invoice_id)
            
            if not invoice:
                # Try to find tenant by customer ID
                tenant = None
                if stripe_invoice.customer:
                    # This would need to be implemented based on how you store customer IDs
                    # For now, we'll skip creating new invoices without tenant context
                    current_app.logger.warning(f"Cannot sync invoice {stripe_invoice_id}: no tenant found")
                    return None
                
                invoice = Invoice.create(
                    tenant_id=tenant.id if tenant else None,
                    stripe_invoice_id=stripe_invoice.id
                )
            
            # Update invoice data
            invoice.stripe_payment_intent_id = stripe_invoice.payment_intent
            invoice.invoice_number = stripe_invoice.number
            invoice.amount_total = Decimal(str(stripe_invoice.total / 100))
            invoice.amount_paid = Decimal(str(stripe_invoice.amount_paid / 100))
            invoice.currency = stripe_invoice.currency.upper()
            invoice.status = stripe_invoice.status
            invoice.invoice_date = datetime.fromtimestamp(stripe_invoice.created).isoformat()
            invoice.due_date = datetime.fromtimestamp(stripe_invoice.due_date).isoformat() if stripe_invoice.due_date else None
            invoice.hosted_invoice_url = stripe_invoice.hosted_invoice_url
            invoice.invoice_pdf_url = stripe_invoice.invoice_pdf
            
            if stripe_invoice.status == 'paid' and stripe_invoice.status_transitions.paid_at:
                invoice.paid_at = datetime.fromtimestamp(
                    stripe_invoice.status_transitions.paid_at
                ).isoformat()
            
            invoice.save()
            return invoice
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error syncing invoice: {str(e)}")
            raise StripeError(f"Failed to sync invoice: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error syncing invoice: {str(e)}")
            raise
    
    def create_payment_link(self, invoice_id: int) -> str:
        """Create a payment link for an invoice."""
        try:
            invoice = Invoice.get_by_id(invoice_id)
            if not invoice:
                raise ValidationError("Invoice not found")
            
            if not invoice.stripe_invoice_id:
                raise ValidationError("Invoice not linked to Stripe")
            
            # Get invoice from Stripe
            stripe_invoice = stripe.Invoice.retrieve(invoice.stripe_invoice_id)
            
            if stripe_invoice.hosted_invoice_url:
                return stripe_invoice.hosted_invoice_url
            
            # If no hosted URL, create a payment link
            payment_link = stripe.PaymentLink.create(
                line_items=[{
                    'price_data': {
                        'currency': invoice.currency.lower(),
                        'product_data': {
                            'name': f'Invoice {invoice.invoice_number or invoice.id}'
                        },
                        'unit_amount': int(invoice.amount_total * 100)
                    },
                    'quantity': 1
                }],
                metadata={
                    'invoice_id': str(invoice.id),
                    'tenant_id': str(invoice.tenant_id)
                }
            )
            
            return payment_link.url
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating payment link: {str(e)}")
            raise StripeError(f"Failed to create payment link: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error creating payment link: {str(e)}")
            raise
    
    def create_customer(self, tenant_id: int, email: str, name: Optional[str] = None, 
                       metadata: Optional[Dict[str, Any]] = None) -> str:
        """Create a Stripe customer."""
        try:
            customer_data = {
                'email': email,
                'metadata': {
                    'tenant_id': str(tenant_id),
                    **(metadata or {})
                }
            }
            
            if name:
                customer_data['name'] = name
            
            customer = stripe.Customer.create(**customer_data)
            
            current_app.logger.info(f"Created Stripe customer {customer.id} for tenant {tenant_id}")
            return customer.id
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating customer: {str(e)}")
            raise StripeError(f"Failed to create customer: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error creating customer: {str(e)}")
            raise
    
    def create_subscription(self, tenant_id: int, customer_id: str, plan_id: int,
                          trial_days: Optional[int] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Subscription:
        """Create a new subscription."""
        try:
            from app.models.billing import Plan
            
            # Get plan
            plan = Plan.get_by_id(plan_id)
            if not plan:
                raise ValidationError("Plan not found")
            
            if not plan.stripe_price_id:
                raise ValidationError("Plan not configured with Stripe price")
            
            # Prepare subscription data
            subscription_data = {
                'customer': customer_id,
                'items': [{
                    'price': plan.stripe_price_id
                }],
                'metadata': {
                    'tenant_id': str(tenant_id),
                    'plan_id': str(plan_id),
                    **(metadata or {})
                }
            }
            
            # Add trial period if specified
            if trial_days:
                subscription_data['trial_period_days'] = trial_days
            
            # Create subscription in Stripe
            stripe_subscription = stripe.Subscription.create(**subscription_data)
            
            # Create local subscription record
            subscription = Subscription.create(
                tenant_id=tenant_id,
                plan_id=plan_id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=customer_id,
                status=stripe_subscription.status,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start).isoformat(),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end).isoformat(),
                trial_start=datetime.fromtimestamp(stripe_subscription.trial_start).isoformat() if stripe_subscription.trial_start else None,
                trial_end=datetime.fromtimestamp(stripe_subscription.trial_end).isoformat() if stripe_subscription.trial_end else None,
                extra_data={
                    'stripe_data': {
                        'id': stripe_subscription.id,
                        'created': stripe_subscription.created,
                        'items': [
                            {
                                'id': item.id,
                                'price': item.price.id,
                                'quantity': item.quantity
                            } for item in stripe_subscription.items.data
                        ]
                    }
                }
            )
            
            # Create entitlements from plan
            from app.models.billing import Entitlement
            Entitlement.create_from_plan(tenant_id, subscription.id, plan)
            
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating subscription: {str(e)}")
            raise StripeError(f"Failed to create subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error creating subscription: {str(e)}")
            raise
    
    def update_subscription(self, subscription_id: int, plan_id: Optional[int] = None,
                          cancel_at_period_end: Optional[bool] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Subscription:
        """Update an existing subscription."""
        try:
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            if not subscription.stripe_subscription_id:
                raise ValidationError("Subscription not linked to Stripe")
            
            # Prepare update data
            update_data = {}
            
            # Change plan if specified
            if plan_id:
                from app.models.billing import Plan
                new_plan = Plan.get_by_id(plan_id)
                if not new_plan:
                    raise ValidationError("New plan not found")
                
                if not new_plan.stripe_price_id:
                    raise ValidationError("New plan not configured with Stripe price")
                
                # Get current subscription from Stripe
                stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                
                # Update subscription items
                update_data['items'] = [{
                    'id': stripe_subscription.items.data[0].id,
                    'price': new_plan.stripe_price_id
                }]
                
                # Update local plan reference
                subscription.plan_id = plan_id
            
            # Set cancellation
            if cancel_at_period_end is not None:
                update_data['cancel_at_period_end'] = cancel_at_period_end
                subscription.cancel_at_period_end = cancel_at_period_end
            
            # Add metadata
            if metadata:
                update_data['metadata'] = metadata
            
            # Update in Stripe if there are changes
            if update_data:
                stripe_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    **update_data
                )
                
                # Update local record
                subscription.status = stripe_subscription.status
                subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start).isoformat()
                subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end).isoformat()
                
                if stripe_subscription.canceled_at:
                    subscription.canceled_at = datetime.fromtimestamp(stripe_subscription.canceled_at).isoformat()
            
            subscription.save()
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error updating subscription: {str(e)}")
            raise StripeError(f"Failed to update subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error updating subscription: {str(e)}")
            raise
    
    def cancel_subscription(self, subscription_id: int, at_period_end: bool = True) -> Subscription:
        """Cancel a subscription."""
        try:
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            if not subscription.stripe_subscription_id:
                raise ValidationError("Subscription not linked to Stripe")
            
            if at_period_end:
                # Cancel at period end
                stripe_subscription = stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    cancel_at_period_end=True
                )
                subscription.cancel_at_period_end = True
            else:
                # Cancel immediately
                stripe_subscription = stripe.Subscription.delete(subscription.stripe_subscription_id)
                subscription.status = 'canceled'
                subscription.canceled_at = datetime.utcnow().isoformat()
            
            subscription.save()
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error canceling subscription: {str(e)}")
            raise StripeError(f"Failed to cancel subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error canceling subscription: {str(e)}")
            raise
    
    def reactivate_subscription(self, subscription_id: int) -> Subscription:
        """Reactivate a canceled subscription."""
        try:
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            if not subscription.stripe_subscription_id:
                raise ValidationError("Subscription not linked to Stripe")
            
            # Remove cancellation
            stripe_subscription = stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                cancel_at_period_end=False
            )
            
            subscription.cancel_at_period_end = False
            subscription.canceled_at = None
            subscription.status = stripe_subscription.status
            subscription.save()
            
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error reactivating subscription: {str(e)}")
            raise StripeError(f"Failed to reactivate subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error reactivating subscription: {str(e)}")
            raise
    
    def sync_subscription_from_stripe(self, stripe_subscription_id: str) -> Optional[Subscription]:
        """Sync subscription data from Stripe."""
        try:
            # Get subscription from Stripe
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            
            # Find or create local subscription
            subscription = Subscription.get_by_stripe_id(stripe_subscription_id)
            
            if not subscription:
                # Try to find tenant by customer ID
                tenant = self._find_tenant_by_customer_id(stripe_subscription.customer)
                if not tenant:
                    current_app.logger.warning(f"Cannot sync subscription {stripe_subscription_id}: no tenant found")
                    return None
                
                # Find plan by price ID
                price_id = stripe_subscription.items.data[0].price.id if stripe_subscription.items.data else None
                plan = None
                if price_id:
                    from app.models.billing import Plan
                    plan = Plan.get_by_stripe_price_id(price_id)
                
                if not plan:
                    current_app.logger.warning(f"Cannot sync subscription {stripe_subscription_id}: no plan found")
                    return None
                
                subscription = Subscription.create(
                    tenant_id=tenant.id,
                    plan_id=plan.id,
                    stripe_subscription_id=stripe_subscription.id,
                    stripe_customer_id=stripe_subscription.customer
                )
            
            # Update subscription data
            subscription.status = stripe_subscription.status
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription.current_period_start).isoformat()
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription.current_period_end).isoformat()
            
            if stripe_subscription.trial_start:
                subscription.trial_start = datetime.fromtimestamp(stripe_subscription.trial_start).isoformat()
            if stripe_subscription.trial_end:
                subscription.trial_end = datetime.fromtimestamp(stripe_subscription.trial_end).isoformat()
            
            if stripe_subscription.canceled_at:
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription.canceled_at).isoformat()
            
            subscription.cancel_at_period_end = stripe_subscription.cancel_at_period_end
            subscription.save()
            
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error syncing subscription: {str(e)}")
            raise StripeError(f"Failed to sync subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error syncing subscription: {str(e)}")
            raise
    
    def record_usage(self, subscription_id: int, event_type: str, quantity: int = 1,
                    metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Record usage for metered billing."""
        try:
            from app.models.billing import UsageEvent, Entitlement
            
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            # Record usage event
            usage_event = UsageEvent.record_usage(
                tenant_id=subscription.tenant_id,
                subscription_id=subscription_id,
                event_type=event_type,
                quantity=quantity,
                **(metadata or {})
            )
            
            # Update entitlement usage
            entitlement = Entitlement.get_by_feature(subscription_id, event_type)
            if entitlement:
                entitlement.increment_usage(quantity)
                entitlement.save()
                
                # Check if over limit
                if entitlement.is_over_limit:
                    current_app.logger.warning(f"Subscription {subscription_id} over limit for {event_type}")
                    
                    # Send notification
                    self._send_usage_notification(subscription, event_type, entitlement)
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error recording usage: {str(e)}")
            return False
    
    def create_stripe_plan(self, name: str, price: Decimal, billing_interval: str = 'month',
                          description: Optional[str] = None,
                          metadata: Optional[Dict[str, Any]] = None) -> Tuple[Any, Any]:
        """Create product and price in Stripe."""
        try:
            # Create product in Stripe
            product_data = {
                'name': name,
                'metadata': metadata or {}
            }
            
            if description:
                product_data['description'] = description
            
            product = stripe.Product.create(**product_data)
            
            # Create price in Stripe
            price_data = {
                'product': product.id,
                'unit_amount': int(price * 100),  # Convert to cents
                'currency': 'usd',
                'recurring': {
                    'interval': billing_interval
                },
                'metadata': metadata or {}
            }
            
            stripe_price = stripe.Price.create(**price_data)
            
            current_app.logger.info(f"Created Stripe product {product.id} and price {stripe_price.id}")
            return product, stripe_price
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating plan: {str(e)}")
            raise StripeError(f"Failed to create Stripe plan: {str(e)}")
    
    def has_valid_payment_method(self, stripe_subscription_id: str) -> bool:
        """Check if subscription has a valid payment method."""
        try:
            # Get subscription from Stripe
            stripe_subscription = stripe.Subscription.retrieve(stripe_subscription_id)
            
            # Get customer
            customer = stripe.Customer.retrieve(stripe_subscription.customer)
            
            # Check for default payment method
            has_payment_method = bool(
                customer.default_source or 
                customer.invoice_settings.default_payment_method
            )
            
            return has_payment_method
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error checking payment method: {str(e)}")
            return False
    
    def _send_usage_notification(self, subscription, event_type: str, entitlement):
        """Send usage limit notifications."""
        try:
            from app.workers.notification_worker import send_notification
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'event_type': 'usage_limit_exceeded',
                'feature': event_type,
                'usage': entitlement.used_value,
                'limit': entitlement.limit_value,
                'usage_percentage': entitlement.usage_percentage
            }
            
            # Queue notification
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='usage_alert',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending usage notification: {str(e)}")
    
    def handle_webhook_event(self, event_type: str, event_data: Dict[str, Any]) -> bool:
        """Handle Stripe webhook events."""
        try:
            # Invoice events
            if event_type == 'invoice.payment_succeeded':
                return self._handle_invoice_payment_succeeded(event_data)
            elif event_type == 'invoice.payment_failed':
                return self._handle_invoice_payment_failed(event_data)
            elif event_type == 'invoice.finalized':
                return self._handle_invoice_finalized(event_data)
            elif event_type == 'invoice.voided':
                return self._handle_invoice_voided(event_data)
            elif event_type == 'invoice.created':
                return self._handle_invoice_created(event_data)
            elif event_type == 'invoice.updated':
                return self._handle_invoice_updated(event_data)
            
            # Subscription events
            elif event_type == 'customer.subscription.created':
                return self._handle_subscription_created(event_data)
            elif event_type == 'customer.subscription.updated':
                return self._handle_subscription_updated(event_data)
            elif event_type == 'customer.subscription.deleted':
                return self._handle_subscription_deleted(event_data)
            elif event_type == 'customer.subscription.trial_will_end':
                return self._handle_subscription_trial_will_end(event_data)
            
            # Payment events
            elif event_type == 'payment_intent.succeeded':
                return self._handle_payment_intent_succeeded(event_data)
            elif event_type == 'payment_intent.payment_failed':
                return self._handle_payment_intent_failed(event_data)
            
            # Customer events
            elif event_type == 'customer.created':
                return self._handle_customer_created(event_data)
            elif event_type == 'customer.updated':
                return self._handle_customer_updated(event_data)
            elif event_type == 'customer.deleted':
                return self._handle_customer_deleted(event_data)
            
            else:
                current_app.logger.info(f"Unhandled webhook event: {event_type}")
                return True
                
        except Exception as e:
            current_app.logger.error(f"Error handling webhook event {event_type}: {str(e)}")
            return False
    
    def _handle_invoice_payment_succeeded(self, event_data: Dict[str, Any]) -> bool:
        """Handle successful invoice payment."""
        stripe_invoice = event_data.get('object')
        if not stripe_invoice:
            return False
        
        invoice = Invoice.get_by_stripe_id(stripe_invoice['id'])
        if invoice:
            invoice.status = 'paid'
            invoice.amount_paid = Decimal(str(stripe_invoice['amount_paid'] / 100))
            invoice.paid_at = datetime.fromtimestamp(
                stripe_invoice['status_transitions']['paid_at']
            ).isoformat()
            invoice.save()
            
            current_app.logger.info(f"Invoice {invoice.id} marked as paid")
        
        return True
    
    def _handle_invoice_payment_failed(self, event_data: Dict[str, Any]) -> bool:
        """Handle failed invoice payment."""
        stripe_invoice = event_data.get('object')
        if not stripe_invoice:
            return False
        
        invoice = Invoice.get_by_stripe_id(stripe_invoice['id'])
        if invoice:
            invoice.status = 'open'  # Keep as open for retry
            invoice.save()
            
            current_app.logger.warning(f"Invoice {invoice.id} payment failed")
        
        return True
    
    def _handle_invoice_finalized(self, event_data: Dict[str, Any]) -> bool:
        """Handle invoice finalization."""
        stripe_invoice = event_data.get('object')
        if not stripe_invoice:
            return False
        
        invoice = Invoice.get_by_stripe_id(stripe_invoice['id'])
        if invoice:
            invoice.status = stripe_invoice['status']
            invoice.invoice_number = stripe_invoice['number']
            invoice.hosted_invoice_url = stripe_invoice['hosted_invoice_url']
            invoice.invoice_pdf_url = stripe_invoice['invoice_pdf']
            invoice.save()
            
            current_app.logger.info(f"Invoice {invoice.id} finalized")
        
        return True
    
    def _handle_invoice_voided(self, event_data: Dict[str, Any]) -> bool:
        """Handle invoice voiding."""
        stripe_invoice = event_data.get('object')
        if not stripe_invoice:
            return False
        
        invoice = Invoice.get_by_stripe_id(stripe_invoice['id'])
        if invoice:
            invoice.status = 'void'
            invoice.save()
            
            current_app.logger.info(f"Invoice {invoice.id} voided")
        
        return True
    
    def _handle_invoice_created(self, event_data: Dict[str, Any]) -> bool:
        """Handle invoice creation."""
        stripe_invoice = event_data.get('object')
        if not stripe_invoice:
            return False
        
        # Sync invoice from Stripe if it doesn't exist locally
        existing_invoice = Invoice.get_by_stripe_id(stripe_invoice['id'])
        if not existing_invoice:
            self.sync_invoice_from_stripe(stripe_invoice['id'])
            current_app.logger.info(f"Synced new invoice {stripe_invoice['id']} from Stripe")
        
        return True
    
    def _handle_invoice_updated(self, event_data: Dict[str, Any]) -> bool:
        """Handle invoice updates."""
        stripe_invoice = event_data.get('object')
        if not stripe_invoice:
            return False
        
        # Sync invoice data from Stripe
        self.sync_invoice_from_stripe(stripe_invoice['id'])
        current_app.logger.info(f"Synced invoice {stripe_invoice['id']} updates from Stripe")
        
        return True
    
    def _handle_subscription_created(self, event_data: Dict[str, Any]) -> bool:
        """Handle subscription creation."""
        stripe_subscription = event_data.get('object')
        if not stripe_subscription:
            return False
        
        try:
            # Find tenant by customer ID
            tenant = self._find_tenant_by_customer_id(stripe_subscription['customer'])
            if not tenant:
                current_app.logger.warning(f"Cannot sync subscription {stripe_subscription['id']}: no tenant found for customer {stripe_subscription['customer']}")
                return True
            
            # Find plan by price ID
            price_id = stripe_subscription['items']['data'][0]['price']['id'] if stripe_subscription['items']['data'] else None
            plan = None
            if price_id:
                from app.models.billing import Plan
                plan = Plan.get_by_stripe_price_id(price_id)
            
            if not plan:
                current_app.logger.warning(f"Cannot sync subscription {stripe_subscription['id']}: no plan found for price {price_id}")
                return True
            
            # Create or update subscription
            subscription = Subscription.get_by_stripe_id(stripe_subscription['id'])
            if not subscription:
                subscription = Subscription.create(
                    tenant_id=tenant.id,
                    plan_id=plan.id,
                    stripe_subscription_id=stripe_subscription['id'],
                    stripe_customer_id=stripe_subscription['customer']
                )
            
            # Update subscription data
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription['current_period_start']).isoformat()
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription['current_period_end']).isoformat()
            
            if stripe_subscription.get('trial_start'):
                subscription.trial_start = datetime.fromtimestamp(stripe_subscription['trial_start']).isoformat()
            if stripe_subscription.get('trial_end'):
                subscription.trial_end = datetime.fromtimestamp(stripe_subscription['trial_end']).isoformat()
            
            if stripe_subscription.get('canceled_at'):
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription['canceled_at']).isoformat()
            
            subscription.cancel_at_period_end = stripe_subscription.get('cancel_at_period_end', False)
            subscription.save()
            
            # Create entitlements from plan
            from app.models.billing import Entitlement
            Entitlement.create_from_plan(tenant.id, subscription.id, plan)
            
            current_app.logger.info(f"Subscription {subscription.id} created/updated from Stripe")
            
            # Send notification
            self._send_subscription_notification(subscription, 'created')
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling subscription creation: {str(e)}")
            return False
    
    def _handle_subscription_updated(self, event_data: Dict[str, Any]) -> bool:
        """Handle subscription updates."""
        stripe_subscription = event_data.get('object')
        if not stripe_subscription:
            return False
        
        try:
            subscription = Subscription.get_by_stripe_id(stripe_subscription['id'])
            if not subscription:
                current_app.logger.warning(f"Subscription {stripe_subscription['id']} not found locally")
                return True
            
            # Store previous status for comparison
            previous_status = subscription.status
            
            # Update subscription data
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = datetime.fromtimestamp(stripe_subscription['current_period_start']).isoformat()
            subscription.current_period_end = datetime.fromtimestamp(stripe_subscription['current_period_end']).isoformat()
            
            if stripe_subscription.get('trial_start'):
                subscription.trial_start = datetime.fromtimestamp(stripe_subscription['trial_start']).isoformat()
            if stripe_subscription.get('trial_end'):
                subscription.trial_end = datetime.fromtimestamp(stripe_subscription['trial_end']).isoformat()
            
            if stripe_subscription.get('canceled_at'):
                subscription.canceled_at = datetime.fromtimestamp(stripe_subscription['canceled_at']).isoformat()
            
            subscription.cancel_at_period_end = stripe_subscription.get('cancel_at_period_end', False)
            subscription.save()
            
            current_app.logger.info(f"Subscription {subscription.id} updated from Stripe")
            
            # Send notification if status changed
            if previous_status != subscription.status:
                self._send_subscription_notification(subscription, 'status_changed', {
                    'previous_status': previous_status,
                    'new_status': subscription.status
                })
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling subscription update: {str(e)}")
            return False
    
    def _handle_subscription_deleted(self, event_data: Dict[str, Any]) -> bool:
        """Handle subscription deletion/cancellation."""
        stripe_subscription = event_data.get('object')
        if not stripe_subscription:
            return False
        
        try:
            subscription = Subscription.get_by_stripe_id(stripe_subscription['id'])
            if not subscription:
                current_app.logger.warning(f"Subscription {stripe_subscription['id']} not found locally")
                return True
            
            # Update subscription status
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.fromtimestamp(stripe_subscription['canceled_at']).isoformat()
            subscription.save()
            
            current_app.logger.info(f"Subscription {subscription.id} canceled")
            
            # Send notification
            self._send_subscription_notification(subscription, 'canceled')
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling subscription deletion: {str(e)}")
            return False
    
    def _handle_subscription_trial_will_end(self, event_data: Dict[str, Any]) -> bool:
        """Handle trial ending soon notification."""
        stripe_subscription = event_data.get('object')
        if not stripe_subscription:
            return False
        
        try:
            subscription = Subscription.get_by_stripe_id(stripe_subscription['id'])
            if not subscription:
                current_app.logger.warning(f"Subscription {stripe_subscription['id']} not found locally")
                return True
            
            current_app.logger.info(f"Trial ending soon for subscription {subscription.id}")
            
            # Send notification
            self._send_subscription_notification(subscription, 'trial_ending')
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling trial ending notification: {str(e)}")
            return False
    
    def _handle_payment_intent_succeeded(self, event_data: Dict[str, Any]) -> bool:
        """Handle successful payment intent."""
        payment_intent = event_data.get('object')
        if not payment_intent:
            return False
        
        try:
            # Find related invoice
            if payment_intent.get('invoice'):
                invoice = Invoice.get_by_stripe_id(payment_intent['invoice'])
                if invoice:
                    # Update payment status
                    invoice.status = 'paid'
                    invoice.amount_paid = Decimal(str(payment_intent['amount_received'] / 100))
                    invoice.paid_at = datetime.fromtimestamp(payment_intent['created']).isoformat()
                    invoice.save()
                    
                    current_app.logger.info(f"Payment succeeded for invoice {invoice.id}")
                    
                    # Send notification
                    self._send_payment_notification(invoice, 'payment_succeeded')
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling payment intent success: {str(e)}")
            return False
    
    def _handle_payment_intent_failed(self, event_data: Dict[str, Any]) -> bool:
        """Handle failed payment intent."""
        payment_intent = event_data.get('object')
        if not payment_intent:
            return False
        
        try:
            # Find related invoice
            if payment_intent.get('invoice'):
                invoice = Invoice.get_by_stripe_id(payment_intent['invoice'])
                if invoice:
                    current_app.logger.warning(f"Payment failed for invoice {invoice.id}")
                    
                    # Send notification
                    self._send_payment_notification(invoice, 'payment_failed', {
                        'failure_reason': payment_intent.get('last_payment_error', {}).get('message', 'Unknown error')
                    })
            
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling payment intent failure: {str(e)}")
            return False
    
    def _handle_customer_created(self, event_data: Dict[str, Any]) -> bool:
        """Handle customer creation."""
        customer = event_data.get('object')
        if not customer:
            return False
        
        current_app.logger.info(f"Customer {customer['id']} created in Stripe")
        return True
    
    def _handle_customer_updated(self, event_data: Dict[str, Any]) -> bool:
        """Handle customer updates."""
        customer = event_data.get('object')
        if not customer:
            return False
        
        current_app.logger.info(f"Customer {customer['id']} updated in Stripe")
        return True
    
    def _handle_customer_deleted(self, event_data: Dict[str, Any]) -> bool:
        """Handle customer deletion."""
        customer = event_data.get('object')
        if not customer:
            return False
        
        current_app.logger.info(f"Customer {customer['id']} deleted in Stripe")
        return True
    
    def _find_tenant_by_customer_id(self, customer_id: str):
        """Find tenant by Stripe customer ID."""
        try:
            # Look for subscription with this customer ID
            subscription = Subscription.query.filter_by(
                stripe_customer_id=customer_id
            ).first()
            
            if subscription:
                from app.models.tenant import Tenant
                return Tenant.get_by_id(subscription.tenant_id)
            
            # If no subscription found, try to get customer from Stripe and check metadata
            try:
                customer = stripe.Customer.retrieve(customer_id)
                if customer.metadata and 'tenant_id' in customer.metadata:
                    tenant_id = int(customer.metadata['tenant_id'])
                    from app.models.tenant import Tenant
                    return Tenant.get_by_id(tenant_id)
            except stripe.error.StripeError:
                pass
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error finding tenant by customer ID: {str(e)}")
            return None
        # For now, we'll look for subscriptions with this customer ID
        subscription = Subscription.query.filter_by(stripe_customer_id=customer_id).first()
        if subscription:
            return subscription.tenant
        return None
    
    def _send_subscription_notification(self, subscription, event_type: str, extra_data: Dict[str, Any] = None):
        """Send subscription-related notifications."""
        try:
            from app.workers.notification_worker import send_notification
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'event_type': event_type,
                'subscription_status': subscription.status,
                'plan_name': subscription.plan.name if subscription.plan else 'Unknown',
                **(extra_data or {})
            }
            
            # Queue notification
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='subscription_update',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending subscription notification: {str(e)}")
    
    def _send_payment_notification(self, invoice, event_type: str, extra_data: Dict[str, Any] = None):
        """Send payment-related notifications."""
        try:
            from app.workers.notification_worker import send_notification
            
            notification_data = {
                'tenant_id': invoice.tenant_id,
                'invoice_id': invoice.id,
                'event_type': event_type,
                'invoice_status': invoice.status,
                'amount': float(invoice.amount_total),
                'currency': invoice.currency,
                **(extra_data or {})
            }
            
            # Queue notification
            send_notification.delay(
                tenant_id=invoice.tenant_id,
                notification_type='payment_update',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending payment notification: {str(e)}")
    
    def create_plan(self, name: str, price: Decimal, billing_interval: str = 'month',
                   features: Optional[Dict[str, Any]] = None,
                   limits: Optional[Dict[str, Any]] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> 'Plan':
        """Create a new subscription plan in Stripe and local database."""
        try:
            from app.models.billing import Plan
            
            # Create product in Stripe
            product = stripe.Product.create(
                name=name,
                metadata=metadata or {}
            )
            
            # Create price in Stripe
            price_data = {
                'product': product.id,
                'unit_amount': int(price * 100),  # Convert to cents
                'currency': 'usd',
                'recurring': {
                    'interval': billing_interval
                },
                'metadata': metadata or {}
            }
            
            stripe_price = stripe.Price.create(**price_data)
            
            # Create local plan record
            plan = Plan.create(
                name=name,
                price=price,
                billing_interval=billing_interval,
                features=features or {},
                limits=limits or {},
                stripe_price_id=stripe_price.id,
                stripe_product_id=product.id,
                is_active=True,
                is_public=True
            )
            
            current_app.logger.info(f"Created plan {plan.id} with Stripe price {stripe_price.id}")
            return plan
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating plan: {str(e)}")
            raise StripeError(f"Failed to create plan: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error creating plan: {str(e)}")
            raise
    
    def update_plan(self, plan_id: int, name: Optional[str] = None,
                   features: Optional[Dict[str, Any]] = None,
                   limits: Optional[Dict[str, Any]] = None,
                   is_active: Optional[bool] = None,
                   metadata: Optional[Dict[str, Any]] = None) -> 'Plan':
        """Update an existing plan."""
        try:
            from app.models.billing import Plan
            
            plan = Plan.get_by_id(plan_id)
            if not plan:
                raise ValidationError("Plan not found")
            
            # Update Stripe product if name changed
            if name and name != plan.name:
                if plan.stripe_product_id:
                    stripe.Product.modify(
                        plan.stripe_product_id,
                        name=name,
                        metadata=metadata or {}
                    )
                plan.name = name
            
            # Update local plan
            if features is not None:
                plan.features = features
            
            if limits is not None:
                plan.limits = limits
            
            if is_active is not None:
                plan.is_active = is_active
            
            plan.save()
            
            current_app.logger.info(f"Updated plan {plan.id}")
            return plan
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error updating plan: {str(e)}")
            raise StripeError(f"Failed to update plan: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error updating plan: {str(e)}")
            raise
    
    def create_trial_subscription(self, tenant_id: int, customer_id: str, plan_id: int,
                                trial_days: int = 3,
                                metadata: Optional[Dict[str, Any]] = None) -> Subscription:
        """Create a subscription with trial period."""
        try:
            from app.models.billing import Plan, Entitlement
            
            # Get plan
            plan = Plan.get_by_id(plan_id)
            if not plan:
                raise ValidationError("Plan not found")
            
            if not plan.stripe_price_id:
                raise ValidationError("Plan not configured with Stripe price")
            
            # Calculate trial end date
            trial_end = datetime.utcnow().timestamp() + (trial_days * 24 * 60 * 60)
            
            # Prepare subscription data
            subscription_data = {
                'customer': customer_id,
                'items': [{
                    'price': plan.stripe_price_id
                }],
                'trial_end': int(trial_end),
                'metadata': {
                    'tenant_id': str(tenant_id),
                    'plan_id': str(plan_id),
                    'trial_days': str(trial_days),
                    **(metadata or {})
                }
            }
            
            # Create subscription in Stripe
            stripe_subscription = stripe.Subscription.create(**subscription_data)
            
            # Create local subscription record
            subscription = Subscription.create(
                tenant_id=tenant_id,
                plan_id=plan_id,
                stripe_subscription_id=stripe_subscription.id,
                stripe_customer_id=customer_id,
                status=stripe_subscription.status,
                current_period_start=datetime.fromtimestamp(stripe_subscription.current_period_start).isoformat(),
                current_period_end=datetime.fromtimestamp(stripe_subscription.current_period_end).isoformat(),
                trial_start=datetime.fromtimestamp(stripe_subscription.trial_start).isoformat(),
                trial_end=datetime.fromtimestamp(stripe_subscription.trial_end).isoformat(),
                extra_data={
                    'trial_days': trial_days,
                    'stripe_data': {
                        'id': stripe_subscription.id,
                        'created': stripe_subscription.created
                    }
                }
            )
            
            # Create entitlements from plan (full access during trial)
            Entitlement.create_from_plan(tenant_id, subscription.id, plan)
            
            current_app.logger.info(f"Created trial subscription {subscription.id} for {trial_days} days")
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error creating trial subscription: {str(e)}")
            raise StripeError(f"Failed to create trial subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error creating trial subscription: {str(e)}")
            raise
    
    def handle_trial_expiration(self, subscription_id: int) -> bool:
        """Handle trial expiration by blocking premium features."""
        try:
            from app.models.billing import Entitlement
            
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            if not subscription.is_trial:
                current_app.logger.warning(f"Subscription {subscription_id} is not in trial")
                return False
            
            # Check if trial has actually expired
            if subscription.trial_end:
                trial_end = datetime.fromisoformat(subscription.trial_end.replace('Z', '+00:00'))
                if datetime.utcnow() < trial_end:
                    current_app.logger.info(f"Trial for subscription {subscription_id} has not expired yet")
                    return False
            
            # Block premium features by setting entitlements to zero
            entitlements = Entitlement.query.filter_by(subscription_id=subscription_id).all()
            for entitlement in entitlements:
                # Keep basic features but limit usage
                if entitlement.feature in ['messages_per_month', 'knowledge_documents', 'leads']:
                    # Set to free tier limits
                    free_limits = {
                        'messages_per_month': 100,
                        'knowledge_documents': 5,
                        'leads': 50
                    }
                    entitlement.limit_value = free_limits.get(entitlement.feature, 0)
                else:
                    # Disable premium features
                    entitlement.limit_value = 0
                
                entitlement.save()
            
            # Update subscription status if still trialing
            if subscription.status == 'trialing':
                subscription.status = 'incomplete'  # Waiting for payment
                subscription.save()
            
            # Send trial expiration notification
            self._send_trial_expiration_notification(subscription)
            
            current_app.logger.info(f"Handled trial expiration for subscription {subscription_id}")
            return True
            
        except Exception as e:
            current_app.logger.error(f"Error handling trial expiration: {str(e)}")
            return False
    
    def upgrade_subscription(self, subscription_id: int, new_plan_id: int,
                           prorate: bool = True) -> Subscription:
        """Upgrade subscription to a new plan."""
        try:
            from app.models.billing import Plan, Entitlement
            
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            new_plan = Plan.get_by_id(new_plan_id)
            if not new_plan:
                raise ValidationError("New plan not found")
            
            if not subscription.stripe_subscription_id:
                raise ValidationError("Subscription not linked to Stripe")
            
            # Get current subscription from Stripe
            stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
            
            # Update subscription items
            stripe.Subscription.modify(
                subscription.stripe_subscription_id,
                items=[{
                    'id': stripe_subscription.items.data[0].id,
                    'price': new_plan.stripe_price_id
                }],
                proration_behavior='create_prorations' if prorate else 'none'
            )
            
            # Update local subscription
            old_plan_id = subscription.plan_id
            subscription.plan_id = new_plan_id
            subscription.save()
            
            # Update entitlements
            Entitlement.query.filter_by(subscription_id=subscription_id).delete()
            Entitlement.create_from_plan(subscription.tenant_id, subscription_id, new_plan)
            
            # Send upgrade notification
            self._send_subscription_upgrade_notification(subscription, old_plan_id, new_plan_id)
            
            current_app.logger.info(f"Upgraded subscription {subscription_id} from plan {old_plan_id} to {new_plan_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error upgrading subscription: {str(e)}")
            raise StripeError(f"Failed to upgrade subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error upgrading subscription: {str(e)}")
            raise
    
    def downgrade_subscription(self, subscription_id: int, new_plan_id: int,
                             at_period_end: bool = True) -> Subscription:
        """Downgrade subscription to a new plan."""
        try:
            from app.models.billing import Plan, Entitlement
            
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            new_plan = Plan.get_by_id(new_plan_id)
            if not new_plan:
                raise ValidationError("New plan not found")
            
            if not subscription.stripe_subscription_id:
                raise ValidationError("Subscription not linked to Stripe")
            
            if at_period_end:
                # Schedule downgrade at period end
                subscription.set_metadata('pending_plan_change', {
                    'new_plan_id': new_plan_id,
                    'change_type': 'downgrade',
                    'scheduled_at': subscription.current_period_end
                })
                subscription.save()
                
                # Send notification about scheduled downgrade
                self._send_subscription_downgrade_scheduled_notification(subscription, new_plan_id)
            else:
                # Immediate downgrade
                stripe_subscription = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
                
                stripe.Subscription.modify(
                    subscription.stripe_subscription_id,
                    items=[{
                        'id': stripe_subscription.items.data[0].id,
                        'price': new_plan.stripe_price_id
                    }],
                    proration_behavior='none'  # No refund for downgrades
                )
                
                # Update local subscription
                old_plan_id = subscription.plan_id
                subscription.plan_id = new_plan_id
                subscription.save()
                
                # Update entitlements
                Entitlement.query.filter_by(subscription_id=subscription_id).delete()
                Entitlement.create_from_plan(subscription.tenant_id, subscription_id, new_plan)
                
                # Send downgrade notification
                self._send_subscription_downgrade_notification(subscription, old_plan_id, new_plan_id)
            
            current_app.logger.info(f"Downgraded subscription {subscription_id} to plan {new_plan_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error downgrading subscription: {str(e)}")
            raise StripeError(f"Failed to downgrade subscription: {str(e)}")
        except Exception as e:
            current_app.logger.error(f"Error downgrading subscription: {str(e)}")
            raise
    
    def handle_usage_overage(self, subscription_id: int, feature: str, 
                           current_usage: int, limit: int) -> bool:
        """Handle usage overage billing."""
        try:
            from app.models.billing import UsageEvent
            
            subscription = Subscription.get_by_id(subscription_id)
            if not subscription:
                raise ValidationError("Subscription not found")
            
            overage_amount = current_usage - limit
            if overage_amount <= 0:
                return True  # No overage
            
            # Calculate overage cost (example: $0.01 per extra message)
            overage_rates = {
                'messages_per_month': 0.01,
                'knowledge_documents': 0.50,
                'leads': 0.10
            }
            
            rate = overage_rates.get(feature, 0.01)
            overage_cost = overage_amount * rate
            
            # Create invoice item for overage
            if subscription.stripe_customer_id and overage_cost > 0:
                stripe.InvoiceItem.create(
                    customer=subscription.stripe_customer_id,
                    amount=int(overage_cost * 100),  # Convert to cents
                    currency='usd',
                    description=f'Overage charges for {feature}: {overage_amount} extra units',
                    metadata={
                        'subscription_id': str(subscription_id),
                        'feature': feature,
                        'overage_amount': str(overage_amount),
                        'rate': str(rate)
                    }
                )
            
            # Record usage event
            UsageEvent.record_usage(
                tenant_id=subscription.tenant_id,
                subscription_id=subscription_id,
                event_type=f'{feature}_overage',
                quantity=overage_amount,
                cost=overage_cost,
                rate=rate
            )
            
            # Send overage notification
            self._send_usage_overage_notification(subscription, feature, overage_amount, overage_cost)
            
            current_app.logger.info(f"Handled overage for subscription {subscription_id}: {feature} +{overage_amount} = ${overage_cost}")
            return True
            
        except stripe.error.StripeError as e:
            current_app.logger.error(f"Stripe error handling overage: {str(e)}")
            return False
        except Exception as e:
            current_app.logger.error(f"Error handling usage overage: {str(e)}")
            return False
    
    def _send_trial_expiration_notification(self, subscription):
        """Send trial expiration notification."""
        try:
            from app.workers.notification_worker import send_notification
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'plan_name': subscription.plan.name if subscription.plan else 'Unknown',
                'trial_end_date': subscription.trial_end
            }
            
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='trial_expired',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending trial expiration notification: {str(e)}")
    
    def _send_subscription_upgrade_notification(self, subscription, old_plan_id, new_plan_id):
        """Send subscription upgrade notification."""
        try:
            from app.workers.notification_worker import send_notification
            from app.models.billing import Plan
            
            old_plan = Plan.get_by_id(old_plan_id)
            new_plan = Plan.get_by_id(new_plan_id)
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'old_plan_name': old_plan.name if old_plan else 'Unknown',
                'new_plan_name': new_plan.name if new_plan else 'Unknown',
                'effective_date': datetime.utcnow().isoformat()
            }
            
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='subscription_upgraded',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending upgrade notification: {str(e)}")
    
    def _send_subscription_downgrade_notification(self, subscription, old_plan_id, new_plan_id):
        """Send subscription downgrade notification."""
        try:
            from app.workers.notification_worker import send_notification
            from app.models.billing import Plan
            
            old_plan = Plan.get_by_id(old_plan_id)
            new_plan = Plan.get_by_id(new_plan_id)
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'old_plan_name': old_plan.name if old_plan else 'Unknown',
                'new_plan_name': new_plan.name if new_plan else 'Unknown',
                'effective_date': datetime.utcnow().isoformat()
            }
            
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='subscription_downgraded',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending downgrade notification: {str(e)}")
    
    def _send_subscription_downgrade_scheduled_notification(self, subscription, new_plan_id):
        """Send scheduled downgrade notification."""
        try:
            from app.workers.notification_worker import send_notification
            from app.models.billing import Plan
            
            new_plan = Plan.get_by_id(new_plan_id)
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'current_plan_name': subscription.plan.name if subscription.plan else 'Unknown',
                'new_plan_name': new_plan.name if new_plan else 'Unknown',
                'effective_date': subscription.current_period_end
            }
            
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='subscription_downgrade_scheduled',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending scheduled downgrade notification: {str(e)}")
    
    def _send_usage_overage_notification(self, subscription, feature, overage_amount, overage_cost):
        """Send usage overage notification."""
        try:
            from app.workers.notification_worker import send_notification
            
            notification_data = {
                'tenant_id': subscription.tenant_id,
                'subscription_id': subscription.id,
                'plan_name': subscription.plan.name if subscription.plan else 'Unknown',
                'feature': feature,
                'overage_amount': overage_amount,
                'overage_cost': overage_cost,
                'billing_date': subscription.current_period_end
            }
            
            send_notification.delay(
                tenant_id=subscription.tenant_id,
                notification_type='usage_overage',
                data=notification_data
            )
            
        except Exception as e:
            current_app.logger.error(f"Error sending overage notification: {str(e)}")