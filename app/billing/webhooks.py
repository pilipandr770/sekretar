"""Stripe webhook handling for billing events."""
import stripe
from flask import request, current_app
from flask_babel import gettext as _
from datetime import datetime
from app.models.billing import Subscription, Invoice, Plan
from app.models.tenant import Tenant
from app.services.stripe_service import StripeService
from app.services.notification_service import NotificationService
from app.utils.decorators import log_api_call
from app.utils.response import success_response, error_response
from app.billing import billing_bp
import structlog

logger = structlog.get_logger()


@billing_bp.route('/webhooks/stripe', methods=['POST'])
@log_api_call('stripe_webhook')
def handle_stripe_webhook():
    """Handle Stripe webhook events."""
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        # Verify webhook signature
        webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        if not webhook_secret:
            logger.warning("Stripe webhook secret not configured")
            return error_response(
                error_code='WEBHOOK_CONFIG_ERROR',
                message='Webhook secret not configured',
                status_code=500
            )
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
        except ValueError as e:
            logger.error("Invalid webhook payload", error=str(e))
            return error_response(
                error_code='WEBHOOK_PAYLOAD_ERROR',
                message='Invalid payload',
                status_code=400
            )
        except stripe.error.SignatureVerificationError as e:
            logger.error("Invalid webhook signature", error=str(e))
            return error_response(
                error_code='WEBHOOK_SIGNATURE_ERROR',
                message='Invalid signature',
                status_code=400
            )
        
        # Process the event
        event_type = event['type']
        event_data = event['data']['object']
        
        logger.info("Processing Stripe webhook", event_type=event_type, event_id=event['id'])
        
        # Route to appropriate handler
        handler_map = {
            # Invoice events
            'invoice.created': handle_invoice_created,
            'invoice.finalized': handle_invoice_finalized,
            'invoice.payment_succeeded': handle_invoice_payment_succeeded,
            'invoice.payment_failed': handle_invoice_payment_failed,
            'invoice.voided': handle_invoice_voided,
            'invoice.updated': handle_invoice_updated,
            
            # Subscription events
            'customer.subscription.created': handle_subscription_created,
            'customer.subscription.updated': handle_subscription_updated,
            'customer.subscription.deleted': handle_subscription_deleted,
            'customer.subscription.trial_will_end': handle_subscription_trial_will_end,
            
            # Payment events
            'payment_intent.succeeded': handle_payment_succeeded,
            'payment_intent.payment_failed': handle_payment_failed,
            
            # Customer events
            'customer.created': handle_customer_created,
            'customer.updated': handle_customer_updated,
            'customer.deleted': handle_customer_deleted,
        }
        
        handler = handler_map.get(event_type)
        if handler:
            success = handler(event_data, event)
            if success:
                logger.info("Webhook processed successfully", event_type=event_type)
                return success_response(
                    message=_('Webhook processed successfully'),
                    data={'event_type': event_type, 'event_id': event['id']}
                )
            else:
                logger.error("Webhook processing failed", event_type=event_type)
                return error_response(
                    error_code='WEBHOOK_PROCESSING_ERROR',
                    message=_('Failed to process webhook'),
                    status_code=500
                )
        else:
            logger.info("Unhandled webhook event", event_type=event_type)
            return success_response(
                message=_('Webhook event ignored'),
                data={'event_type': event_type, 'event_id': event['id']}
            )
        
    except Exception as e:
        logger.error("Error handling webhook", error=str(e))
        return error_response(
            error_code='WEBHOOK_ERROR',
            message=_('Webhook processing failed'),
            status_code=500
        )


def handle_invoice_created(invoice_data, event):
    """Handle invoice.created event."""
    try:
        stripe_service = StripeService()
        invoice = stripe_service.sync_invoice_from_stripe(invoice_data['id'])
        
        if invoice:
            logger.info("Invoice created", invoice_id=invoice.id, stripe_id=invoice_data['id'])
            
            # Send notification if configured
            notification_service = NotificationService()
            notification_service.send_invoice_created_notification(invoice)
        
        return True
        
    except Exception as e:
        logger.error("Error handling invoice.created", error=str(e), stripe_id=invoice_data['id'])
        return False


def handle_invoice_finalized(invoice_data, event):
    """Handle invoice.finalized event."""
    try:
        invoice = Invoice.get_by_stripe_id(invoice_data['id'])
        if not invoice:
            # Try to sync from Stripe
            stripe_service = StripeService()
            invoice = stripe_service.sync_invoice_from_stripe(invoice_data['id'])
        
        if invoice:
            invoice.status = invoice_data['status']
            invoice.invoice_number = invoice_data.get('number')
            invoice.hosted_invoice_url = invoice_data.get('hosted_invoice_url')
            invoice.invoice_pdf_url = invoice_data.get('invoice_pdf')
            invoice.save()
            
            logger.info("Invoice finalized", invoice_id=invoice.id, stripe_id=invoice_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_invoice_finalized_notification(invoice)
        
        return True
        
    except Exception as e:
        logger.error("Error handling invoice.finalized", error=str(e), stripe_id=invoice_data['id'])
        return False


def handle_invoice_payment_succeeded(invoice_data, event):
    """Handle invoice.payment_succeeded event."""
    try:
        invoice = Invoice.get_by_stripe_id(invoice_data['id'])
        if not invoice:
            # Try to sync from Stripe
            stripe_service = StripeService()
            invoice = stripe_service.sync_invoice_from_stripe(invoice_data['id'])
        
        if invoice:
            invoice.status = 'paid'
            invoice.amount_paid = invoice_data['amount_paid'] / 100  # Convert from cents
            invoice.paid_at = datetime.fromtimestamp(
                invoice_data['status_transitions']['paid_at']
            ).isoformat()
            invoice.save()
            
            logger.info("Invoice payment succeeded", invoice_id=invoice.id, stripe_id=invoice_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_invoice_paid_notification(invoice)
            
            # Update subscription status if applicable
            if invoice.subscription_id:
                subscription = invoice.subscription
                if subscription and subscription.status == 'past_due':
                    subscription.status = 'active'
                    subscription.save()
                    logger.info("Subscription reactivated after payment", subscription_id=subscription.id)
        
        return True
        
    except Exception as e:
        logger.error("Error handling invoice.payment_succeeded", error=str(e), stripe_id=invoice_data['id'])
        return False


def handle_invoice_payment_failed(invoice_data, event):
    """Handle invoice.payment_failed event."""
    try:
        invoice = Invoice.get_by_stripe_id(invoice_data['id'])
        if not invoice:
            # Try to sync from Stripe
            stripe_service = StripeService()
            invoice = stripe_service.sync_invoice_from_stripe(invoice_data['id'])
        
        if invoice:
            invoice.status = invoice_data['status']  # Usually 'open' or 'past_due'
            invoice.save()
            
            logger.warning("Invoice payment failed", invoice_id=invoice.id, stripe_id=invoice_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_invoice_payment_failed_notification(invoice)
            
            # Update subscription status if applicable
            if invoice.subscription_id:
                subscription = invoice.subscription
                if subscription:
                    subscription.status = 'past_due'
                    subscription.save()
                    logger.warning("Subscription marked as past due", subscription_id=subscription.id)
        
        return True
        
    except Exception as e:
        logger.error("Error handling invoice.payment_failed", error=str(e), stripe_id=invoice_data['id'])
        return False


def handle_invoice_voided(invoice_data, event):
    """Handle invoice.voided event."""
    try:
        invoice = Invoice.get_by_stripe_id(invoice_data['id'])
        if invoice:
            invoice.status = 'void'
            invoice.save()
            
            logger.info("Invoice voided", invoice_id=invoice.id, stripe_id=invoice_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_invoice_voided_notification(invoice)
        
        return True
        
    except Exception as e:
        logger.error("Error handling invoice.voided", error=str(e), stripe_id=invoice_data['id'])
        return False


def handle_invoice_updated(invoice_data, event):
    """Handle invoice.updated event."""
    try:
        invoice = Invoice.get_by_stripe_id(invoice_data['id'])
        if invoice:
            # Update relevant fields
            invoice.status = invoice_data['status']
            invoice.amount_total = invoice_data['total'] / 100  # Convert from cents
            invoice.amount_paid = invoice_data['amount_paid'] / 100
            invoice.hosted_invoice_url = invoice_data.get('hosted_invoice_url')
            invoice.invoice_pdf_url = invoice_data.get('invoice_pdf')
            
            if invoice_data.get('due_date'):
                invoice.due_date = datetime.fromtimestamp(invoice_data['due_date']).isoformat()
            
            invoice.save()
            
            logger.info("Invoice updated", invoice_id=invoice.id, stripe_id=invoice_data['id'])
        
        return True
        
    except Exception as e:
        logger.error("Error handling invoice.updated", error=str(e), stripe_id=invoice_data['id'])
        return False


def handle_subscription_created(subscription_data, event):
    """Handle customer.subscription.created event."""
    try:
        stripe_service = StripeService()
        subscription = stripe_service.sync_subscription_from_stripe(subscription_data['id'])
        
        if subscription:
            logger.info("Subscription created", subscription_id=subscription.id, stripe_id=subscription_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_subscription_created_notification(subscription)
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.subscription.created", error=str(e), stripe_id=subscription_data['id'])
        return False


def handle_subscription_updated(subscription_data, event):
    """Handle customer.subscription.updated event."""
    try:
        subscription = Subscription.get_by_stripe_id(subscription_data['id'])
        if not subscription:
            # Try to sync from Stripe
            stripe_service = StripeService()
            subscription = stripe_service.sync_subscription_from_stripe(subscription_data['id'])
        
        if subscription:
            # Update subscription data
            old_status = subscription.status
            subscription.status = subscription_data['status']
            subscription.current_period_start = datetime.fromtimestamp(
                subscription_data['current_period_start']
            ).isoformat()
            subscription.current_period_end = datetime.fromtimestamp(
                subscription_data['current_period_end']
            ).isoformat()
            subscription.cancel_at_period_end = subscription_data.get('cancel_at_period_end', False)
            
            if subscription_data.get('canceled_at'):
                subscription.canceled_at = datetime.fromtimestamp(
                    subscription_data['canceled_at']
                ).isoformat()
            
            if subscription_data.get('trial_start'):
                subscription.trial_start = datetime.fromtimestamp(
                    subscription_data['trial_start']
                ).isoformat()
            
            if subscription_data.get('trial_end'):
                subscription.trial_end = datetime.fromtimestamp(
                    subscription_data['trial_end']
                ).isoformat()
            
            subscription.save()
            
            logger.info("Subscription updated", 
                       subscription_id=subscription.id, 
                       stripe_id=subscription_data['id'],
                       old_status=old_status,
                       new_status=subscription.status)
            
            # Send notifications for status changes
            notification_service = NotificationService()
            if old_status != subscription.status:
                if subscription.status == 'canceled':
                    notification_service.send_subscription_canceled_notification(subscription)
                elif subscription.status == 'active' and old_status in ['past_due', 'unpaid']:
                    notification_service.send_subscription_reactivated_notification(subscription)
                elif subscription.status in ['past_due', 'unpaid']:
                    notification_service.send_subscription_payment_failed_notification(subscription)
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.subscription.updated", error=str(e), stripe_id=subscription_data['id'])
        return False


def handle_subscription_deleted(subscription_data, event):
    """Handle customer.subscription.deleted event."""
    try:
        subscription = Subscription.get_by_stripe_id(subscription_data['id'])
        if subscription:
            subscription.status = 'canceled'
            subscription.canceled_at = datetime.utcnow().isoformat()
            subscription.save()
            
            logger.info("Subscription deleted", subscription_id=subscription.id, stripe_id=subscription_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_subscription_canceled_notification(subscription)
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.subscription.deleted", error=str(e), stripe_id=subscription_data['id'])
        return False


def handle_subscription_trial_will_end(subscription_data, event):
    """Handle customer.subscription.trial_will_end event."""
    try:
        subscription = Subscription.get_by_stripe_id(subscription_data['id'])
        if subscription:
            logger.info("Subscription trial ending soon", subscription_id=subscription.id, stripe_id=subscription_data['id'])
            
            # Send notification
            notification_service = NotificationService()
            notification_service.send_trial_ending_notification(subscription)
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.subscription.trial_will_end", error=str(e), stripe_id=subscription_data['id'])
        return False


def handle_payment_succeeded(payment_intent_data, event):
    """Handle payment_intent.succeeded event."""
    try:
        # Find associated invoice
        invoice_id = payment_intent_data.get('invoice')
        if invoice_id:
            invoice = Invoice.get_by_stripe_id(invoice_id)
            if invoice:
                logger.info("Payment succeeded for invoice", 
                           invoice_id=invoice.id, 
                           payment_intent_id=payment_intent_data['id'])
                
                # Update payment intent ID
                invoice.stripe_payment_intent_id = payment_intent_data['id']
                invoice.save()
        
        return True
        
    except Exception as e:
        logger.error("Error handling payment_intent.succeeded", error=str(e), payment_intent_id=payment_intent_data['id'])
        return False


def handle_payment_failed(payment_intent_data, event):
    """Handle payment_intent.payment_failed event."""
    try:
        # Find associated invoice
        invoice_id = payment_intent_data.get('invoice')
        if invoice_id:
            invoice = Invoice.get_by_stripe_id(invoice_id)
            if invoice:
                logger.warning("Payment failed for invoice", 
                              invoice_id=invoice.id, 
                              payment_intent_id=payment_intent_data['id'])
                
                # Update payment intent ID
                invoice.stripe_payment_intent_id = payment_intent_data['id']
                invoice.save()
                
                # Send notification
                notification_service = NotificationService()
                notification_service.send_payment_failed_notification(invoice)
        
        return True
        
    except Exception as e:
        logger.error("Error handling payment_intent.payment_failed", error=str(e), payment_intent_id=payment_intent_data['id'])
        return False


def handle_customer_created(customer_data, event):
    """Handle customer.created event."""
    try:
        logger.info("Customer created", customer_id=customer_data['id'], email=customer_data.get('email'))
        
        # Store customer information if needed
        tenant_id = customer_data.get('metadata', {}).get('tenant_id')
        if tenant_id:
            tenant = Tenant.get_by_id(int(tenant_id))
            if tenant:
                # Update tenant with customer ID if not already set
                if not tenant.get_metadata('stripe_customer_id'):
                    tenant.set_metadata('stripe_customer_id', customer_data['id'])
                    tenant.save()
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.created", error=str(e), customer_id=customer_data['id'])
        return False


def handle_customer_updated(customer_data, event):
    """Handle customer.updated event."""
    try:
        logger.info("Customer updated", customer_id=customer_data['id'], email=customer_data.get('email'))
        
        # Update customer information if needed
        tenant_id = customer_data.get('metadata', {}).get('tenant_id')
        if tenant_id:
            tenant = Tenant.get_by_id(int(tenant_id))
            if tenant:
                # Update tenant metadata
                tenant.set_metadata('stripe_customer_email', customer_data.get('email'))
                tenant.set_metadata('stripe_customer_name', customer_data.get('name'))
                tenant.save()
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.updated", error=str(e), customer_id=customer_data['id'])
        return False


def handle_customer_deleted(customer_data, event):
    """Handle customer.deleted event."""
    try:
        logger.info("Customer deleted", customer_id=customer_data['id'])
        
        # Clean up customer references
        tenant_id = customer_data.get('metadata', {}).get('tenant_id')
        if tenant_id:
            tenant = Tenant.get_by_id(int(tenant_id))
            if tenant:
                # Remove customer ID from tenant
                tenant.set_metadata('stripe_customer_id', None)
                tenant.save()
        
        return True
        
    except Exception as e:
        logger.error("Error handling customer.deleted", error=str(e), customer_id=customer_data['id'])
        return False