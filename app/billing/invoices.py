"""Invoice management API endpoints."""
from flask import request, g, current_app
from flask_babel import gettext as _
from decimal import Decimal
from datetime import datetime, timedelta
from sqlalchemy import desc, asc, and_, or_
from app.models.billing import Invoice, Subscription
from app.models.tenant import Tenant
from app.services.stripe_service import StripeService
from app.utils.decorators import (
    require_json, require_tenant, require_role, require_permission,
    require_active_subscription, log_api_call, validate_pagination
)
from app.utils.response import (
    success_response, error_response, not_found_response,
    validation_error_response, paginated_response
)
from app.utils.exceptions import StripeError, ValidationError
from app.billing import billing_bp
import structlog

logger = structlog.get_logger()


@billing_bp.route('/invoices', methods=['GET'])
@require_tenant()
@require_permission('invoice:read')
@validate_pagination()
@log_api_call('list_invoices')
def list_invoices():
    """List invoices for the current tenant with filtering and pagination."""
    try:
        tenant_id = g.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Get query parameters for filtering
        status = request.args.get('status')
        subscription_id = request.args.get('subscription_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query
        query = Invoice.query.filter_by(tenant_id=tenant_id)
        
        # Apply filters
        if status:
            query = query.filter(Invoice.status == status)
        
        if subscription_id:
            try:
                sub_id = int(subscription_id)
                query = query.filter(Invoice.subscription_id == sub_id)
            except ValueError:
                return validation_error_response([{
                    'field': 'subscription_id',
                    'message': _('Invalid subscription ID')
                }])
        
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Invoice.created_at >= start)
            except ValueError:
                return validation_error_response([{
                    'field': 'start_date',
                    'message': _('Invalid date format. Use ISO 8601 format.')
                }])
        
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Invoice.created_at <= end)
            except ValueError:
                return validation_error_response([{
                    'field': 'end_date',
                    'message': _('Invalid date format. Use ISO 8601 format.')
                }])
        
        # Apply sorting
        sort_column = getattr(Invoice, sort_by, None)
        if sort_column is None:
            sort_column = Invoice.created_at
        
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(sort_column))
        else:
            query = query.order_by(desc(sort_column))
        
        # Execute paginated query
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Convert to dict
        invoices = [invoice.to_dict() for invoice in pagination.items]
        
        # Add summary statistics
        total_amount = sum(float(invoice.get('amount_total', 0)) for invoice in invoices)
        paid_amount = sum(float(invoice.get('amount_paid', 0)) for invoice in invoices)
        
        return paginated_response(
            items=invoices,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Invoices retrieved successfully'),
            summary={
                'total_amount': total_amount,
                'paid_amount': paid_amount,
                'outstanding_amount': total_amount - paid_amount,
                'currency': 'USD'  # TODO: Support multiple currencies
            }
        )
        
    except Exception as e:
        logger.error("Error listing invoices", error=str(e), tenant_id=g.tenant_id)
        return error_response(
            error_code='INVOICE_LIST_ERROR',
            message=_('Failed to retrieve invoices'),
            status_code=500
        )


@billing_bp.route('/invoices/<int:invoice_id>', methods=['GET'])
@require_tenant()
@require_permission('invoice:read')
@log_api_call('get_invoice')
def get_invoice(invoice_id):
    """Get a specific invoice by ID."""
    try:
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not invoice:
            return not_found_response('Invoice')
        
        return success_response(
            message=_('Invoice retrieved successfully'),
            data=invoice.to_dict()
        )
        
    except Exception as e:
        logger.error("Error getting invoice", error=str(e), invoice_id=invoice_id)
        return error_response(
            error_code='INVOICE_GET_ERROR',
            message=_('Failed to retrieve invoice'),
            status_code=500
        )


@billing_bp.route('/invoices', methods=['POST'])
@require_tenant()
@require_permission('invoice:create')
@require_json(['customer_id'])
@log_api_call('create_invoice')
def create_invoice():
    """Create a new invoice."""
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        # Validate required fields
        customer_id = data.get('customer_id')
        if not customer_id:
            return validation_error_response([{
                'field': 'customer_id',
                'message': _('Customer ID is required')
            }])
        
        # Optional fields
        subscription_id = data.get('subscription_id')
        amount = data.get('amount')
        currency = data.get('currency', 'USD')
        description = data.get('description')
        metadata = data.get('metadata', {})
        
        # Validate amount if provided
        if amount is not None:
            try:
                amount = Decimal(str(amount))
                if amount <= 0:
                    return validation_error_response([{
                        'field': 'amount',
                        'message': _('Amount must be positive')
                    }])
            except (ValueError, TypeError):
                return validation_error_response([{
                    'field': 'amount',
                    'message': _('Invalid amount format')
                }])
        
        # Validate subscription if provided
        if subscription_id:
            subscription = Subscription.query.filter_by(
                id=subscription_id,
                tenant_id=tenant_id
            ).first()
            if not subscription:
                return validation_error_response([{
                    'field': 'subscription_id',
                    'message': _('Subscription not found')
                }])
        
        # Create invoice using Stripe service
        stripe_service = StripeService()
        invoice = stripe_service.create_invoice(
            tenant_id=tenant_id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            amount=amount,
            currency=currency,
            description=description,
            metadata=metadata
        )
        
        return success_response(
            message=_('Invoice created successfully'),
            data=invoice.to_dict(),
            status_code=201
        )
        
    except StripeError as e:
        logger.error("Stripe error creating invoice", error=str(e))
        return error_response(
            error_code='STRIPE_ERROR',
            message=str(e),
            status_code=400
        )
    except ValidationError as e:
        return validation_error_response([{
            'field': 'general',
            'message': str(e)
        }])
    except Exception as e:
        logger.error("Error creating invoice", error=str(e))
        return error_response(
            error_code='INVOICE_CREATE_ERROR',
            message=_('Failed to create invoice'),
            status_code=500
        )


@billing_bp.route('/invoices/<int:invoice_id>/finalize', methods=['POST'])
@require_tenant()
@require_permission('invoice:update')
@log_api_call('finalize_invoice')
def finalize_invoice(invoice_id):
    """Finalize a draft invoice."""
    try:
        # Check if invoice exists and belongs to tenant
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not invoice:
            return not_found_response('Invoice')
        
        if invoice.status != 'draft':
            return error_response(
                error_code='INVOICE_STATE_ERROR',
                message=_('Only draft invoices can be finalized'),
                status_code=400
            )
        
        # Finalize using Stripe service
        stripe_service = StripeService()
        updated_invoice = stripe_service.finalize_invoice(invoice_id)
        
        return success_response(
            message=_('Invoice finalized successfully'),
            data=updated_invoice.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error finalizing invoice", error=str(e))
        return error_response(
            error_code='STRIPE_ERROR',
            message=str(e),
            status_code=400
        )
    except ValidationError as e:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Error finalizing invoice", error=str(e), invoice_id=invoice_id)
        return error_response(
            error_code='INVOICE_FINALIZE_ERROR',
            message=_('Failed to finalize invoice'),
            status_code=500
        )


@billing_bp.route('/invoices/<int:invoice_id>/send', methods=['POST'])
@require_tenant()
@require_permission('invoice:update')
@log_api_call('send_invoice')
def send_invoice(invoice_id):
    """Send invoice to customer."""
    try:
        # Check if invoice exists and belongs to tenant
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not invoice:
            return not_found_response('Invoice')
        
        if invoice.status not in ['open', 'draft']:
            return error_response(
                error_code='INVOICE_STATE_ERROR',
                message=_('Only open or draft invoices can be sent'),
                status_code=400
            )
        
        # Send using Stripe service
        stripe_service = StripeService()
        updated_invoice = stripe_service.send_invoice(invoice_id)
        
        return success_response(
            message=_('Invoice sent successfully'),
            data=updated_invoice.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error sending invoice", error=str(e))
        return error_response(
            error_code='STRIPE_ERROR',
            message=str(e),
            status_code=400
        )
    except ValidationError as e:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Error sending invoice", error=str(e), invoice_id=invoice_id)
        return error_response(
            error_code='INVOICE_SEND_ERROR',
            message=_('Failed to send invoice'),
            status_code=500
        )


@billing_bp.route('/invoices/<int:invoice_id>/void', methods=['POST'])
@require_tenant()
@require_permission('invoice:update')
@log_api_call('void_invoice')
def void_invoice(invoice_id):
    """Void an invoice."""
    try:
        # Check if invoice exists and belongs to tenant
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not invoice:
            return not_found_response('Invoice')
        
        if invoice.status in ['paid', 'void']:
            return error_response(
                error_code='INVOICE_STATE_ERROR',
                message=_('Paid or voided invoices cannot be voided'),
                status_code=400
            )
        
        # Void using Stripe service
        stripe_service = StripeService()
        updated_invoice = stripe_service.void_invoice(invoice_id)
        
        return success_response(
            message=_('Invoice voided successfully'),
            data=updated_invoice.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error voiding invoice", error=str(e))
        return error_response(
            error_code='STRIPE_ERROR',
            message=str(e),
            status_code=400
        )
    except ValidationError as e:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Error voiding invoice", error=str(e), invoice_id=invoice_id)
        return error_response(
            error_code='INVOICE_VOID_ERROR',
            message=_('Failed to void invoice'),
            status_code=500
        )


@billing_bp.route('/invoices/<int:invoice_id>/status', methods=['GET'])
@require_tenant()
@require_permission('invoice:read')
@log_api_call('get_invoice_status')
def get_invoice_status(invoice_id):
    """Get current invoice status from Stripe."""
    try:
        # Check if invoice exists and belongs to tenant
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not invoice:
            return not_found_response('Invoice')
        
        # Get status using Stripe service
        stripe_service = StripeService()
        status_data = stripe_service.get_invoice_status(invoice_id)
        
        return success_response(
            message=_('Invoice status retrieved successfully'),
            data=status_data
        )
        
    except StripeError as e:
        logger.error("Stripe error getting invoice status", error=str(e))
        return error_response(
            error_code='STRIPE_ERROR',
            message=str(e),
            status_code=400
        )
    except ValidationError as e:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Error getting invoice status", error=str(e), invoice_id=invoice_id)
        return error_response(
            error_code='INVOICE_STATUS_ERROR',
            message=_('Failed to get invoice status'),
            status_code=500
        )


@billing_bp.route('/invoices/<int:invoice_id>/payment-link', methods=['POST'])
@require_tenant()
@require_permission('invoice:read')
@log_api_call('create_payment_link')
def create_payment_link(invoice_id):
    """Create a payment link for an invoice."""
    try:
        # Check if invoice exists and belongs to tenant
        invoice = Invoice.query.filter_by(
            id=invoice_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not invoice:
            return not_found_response('Invoice')
        
        if invoice.status in ['paid', 'void']:
            return error_response(
                error_code='INVOICE_STATE_ERROR',
                message=_('Payment links cannot be created for paid or voided invoices'),
                status_code=400
            )
        
        # Create payment link using Stripe service
        stripe_service = StripeService()
        payment_url = stripe_service.create_payment_link(invoice_id)
        
        return success_response(
            message=_('Payment link created successfully'),
            data={
                'payment_url': payment_url,
                'invoice_id': invoice_id
            }
        )
        
    except StripeError as e:
        logger.error("Stripe error creating payment link", error=str(e))
        return error_response(
            error_code='STRIPE_ERROR',
            message=str(e),
            status_code=400
        )
    except ValidationError as e:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Error creating payment link", error=str(e), invoice_id=invoice_id)
        return error_response(
            error_code='PAYMENT_LINK_ERROR',
            message=_('Failed to create payment link'),
            status_code=500
        )


@billing_bp.route('/invoices/reports/summary', methods=['GET'])
@require_tenant()
@require_permission('invoice:read')
@log_api_call('get_invoice_summary')
def get_invoice_summary():
    """Get invoice summary and statistics."""
    try:
        tenant_id = g.tenant_id
        
        # Get query parameters for date range
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build base query
        query = Invoice.query.filter_by(tenant_id=tenant_id)
        
        # Apply date filters
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(Invoice.created_at >= start)
            except ValueError:
                return validation_error_response([{
                    'field': 'start_date',
                    'message': _('Invalid date format. Use ISO 8601 format.')
                }])
        
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(Invoice.created_at <= end)
            except ValueError:
                return validation_error_response([{
                    'field': 'end_date',
                    'message': _('Invalid date format. Use ISO 8601 format.')
                }])
        
        # Get all invoices for the period
        invoices = query.all()
        
        # Calculate summary statistics
        total_invoices = len(invoices)
        total_amount = sum(float(invoice.amount_total) for invoice in invoices)
        paid_amount = sum(float(invoice.amount_paid) for invoice in invoices)
        outstanding_amount = total_amount - paid_amount
        
        # Status breakdown
        status_counts = {}
        for invoice in invoices:
            status = invoice.status
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Overdue invoices
        overdue_invoices = [invoice for invoice in invoices if invoice.is_overdue]
        overdue_amount = sum(float(invoice.amount_due) for invoice in overdue_invoices)
        
        # Monthly breakdown (last 12 months)
        monthly_data = {}
        for invoice in invoices:
            if invoice.created_at:
                month_key = invoice.created_at.strftime('%Y-%m')
                if month_key not in monthly_data:
                    monthly_data[month_key] = {
                        'count': 0,
                        'total_amount': 0,
                        'paid_amount': 0
                    }
                monthly_data[month_key]['count'] += 1
                monthly_data[month_key]['total_amount'] += float(invoice.amount_total)
                monthly_data[month_key]['paid_amount'] += float(invoice.amount_paid)
        
        summary_data = {
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            'totals': {
                'invoice_count': total_invoices,
                'total_amount': total_amount,
                'paid_amount': paid_amount,
                'outstanding_amount': outstanding_amount,
                'overdue_amount': overdue_amount,
                'currency': 'USD'  # TODO: Support multiple currencies
            },
            'status_breakdown': status_counts,
            'overdue': {
                'count': len(overdue_invoices),
                'amount': overdue_amount
            },
            'monthly_breakdown': monthly_data
        }
        
        return success_response(
            message=_('Invoice summary retrieved successfully'),
            data=summary_data
        )
        
    except Exception as e:
        logger.error("Error getting invoice summary", error=str(e), tenant_id=g.tenant_id)
        return error_response(
            error_code='INVOICE_SUMMARY_ERROR',
            message=_('Failed to retrieve invoice summary'),
            status_code=500
        )


@billing_bp.route('/invoices/webhook', methods=['POST'])
@log_api_call('handle_invoice_webhook')
def handle_invoice_webhook():
    """Handle Stripe webhook events for invoice updates."""
    try:
        payload = request.get_data()
        sig_header = request.headers.get('Stripe-Signature')
        
        # Verify webhook signature (if configured)
        webhook_secret = current_app.config.get('STRIPE_WEBHOOK_SECRET')
        if webhook_secret:
            try:
                import stripe
                event = stripe.Webhook.construct_event(
                    payload, sig_header, webhook_secret
                )
            except ValueError:
                logger.error("Invalid webhook payload")
                return error_response(
                    error_code='WEBHOOK_ERROR',
                    message='Invalid payload',
                    status_code=400
                )
            except stripe.error.SignatureVerificationError:
                logger.error("Invalid webhook signature")
                return error_response(
                    error_code='WEBHOOK_ERROR',
                    message='Invalid signature',
                    status_code=400
                )
        else:
            # Parse JSON if no signature verification
            try:
                event = request.get_json()
            except Exception:
                return error_response(
                    error_code='WEBHOOK_ERROR',
                    message='Invalid JSON',
                    status_code=400
                )
        
        # Handle the event
        stripe_service = StripeService()
        success = stripe_service.handle_webhook_event(
            event['type'],
            event['data']
        )
        
        if success:
            return success_response(
                message=_('Webhook processed successfully'),
                data={'event_type': event['type']}
            )
        else:
            return error_response(
                error_code='WEBHOOK_PROCESSING_ERROR',
                message=_('Failed to process webhook'),
                status_code=500
            )
        
    except Exception as e:
        logger.error("Error handling webhook", error=str(e))
        return error_response(
            error_code='WEBHOOK_ERROR',
            message=_('Webhook processing failed'),
            status_code=500
        )