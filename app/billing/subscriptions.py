"""Subscription management API endpoints."""
from flask import request, g, current_app
from flask_babel import gettext as _
from datetime import datetime, timedelta
from sqlalchemy import desc, asc, and_, or_
from app.models.billing import Subscription, Plan, UsageEvent, Entitlement
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


@billing_bp.route('/subscriptions', methods=['GET'])
@require_tenant()
@require_permission('subscription:read')
@validate_pagination()
@log_api_call('list_subscriptions')
def list_subscriptions():
    """List subscriptions for the current tenant."""
    try:
        tenant_id = g.tenant_id
        page = g.page
        per_page = g.per_page
        
        # Get query parameters for filtering
        status = request.args.get('status')
        plan_id = request.args.get('plan_id')
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Build query
        query = Subscription.query.filter_by(tenant_id=tenant_id)
        
        # Apply filters
        if status:
            query = query.filter(Subscription.status == status)
        
        if plan_id:
            try:
                p_id = int(plan_id)
                query = query.filter(Subscription.plan_id == p_id)
            except ValueError:
                return validation_error_response([{
                    'field': 'plan_id',
                    'message': _('Invalid plan ID')
                }])
        
        # Apply sorting
        sort_column = getattr(Subscription, sort_by, None)
        if sort_column is None:
            sort_column = Subscription.created_at
        
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
        subscriptions = [subscription.to_dict() for subscription in pagination.items]
        
        return paginated_response(
            items=subscriptions,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Subscriptions retrieved successfully')
        )
        
    except Exception as e:
        logger.error("Error listing subscriptions", error=str(e), tenant_id=g.tenant_id)
        return error_response(
            error_code='SUBSCRIPTION_LIST_ERROR',
            message=_('Failed to retrieve subscriptions'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>', methods=['GET'])
@require_tenant()
@require_permission('subscription:read')
@log_api_call('get_subscription')
def get_subscription(subscription_id):
    """Get a specific subscription by ID."""
    try:
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Include usage data
        subscription_data = subscription.to_dict()
        
        # Add current usage information
        entitlements = Entitlement.query.filter_by(subscription_id=subscription_id).all()
        subscription_data['entitlements'] = [entitlement.to_dict() for entitlement in entitlements]
        
        # Add recent usage events
        recent_usage = UsageEvent.query.filter_by(
            subscription_id=subscription_id
        ).order_by(desc(UsageEvent.created_at)).limit(10).all()
        subscription_data['recent_usage'] = [event.to_dict() for event in recent_usage]
        
        return success_response(
            message=_('Subscription retrieved successfully'),
            data=subscription_data
        )
        
    except Exception as e:
        logger.error("Error getting subscription", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_GET_ERROR',
            message=_('Failed to retrieve subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions', methods=['POST'])
@require_tenant()
@require_permission('subscription:create')
@require_json(['plan_id', 'customer_email'])
@log_api_call('create_subscription')
def create_subscription():
    """Create a new subscription."""
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        # Validate required fields
        plan_id = data.get('plan_id')
        customer_email = data.get('customer_email')
        
        if not plan_id or not customer_email:
            return validation_error_response([{
                'field': 'general',
                'message': _('Plan ID and customer email are required')
            }])
        
        # Validate plan
        plan = Plan.get_by_id(plan_id)
        if not plan or not plan.is_active:
            return validation_error_response([{
                'field': 'plan_id',
                'message': _('Invalid or inactive plan')
            }])
        
        # Optional fields
        customer_name = data.get('customer_name')
        trial_days = data.get('trial_days', 3)  # Default 3-day trial
        metadata = data.get('metadata', {})
        
        # Create Stripe service
        stripe_service = StripeService()
        
        # Create or get customer
        customer_id = data.get('customer_id')
        if not customer_id:
            customer_id = stripe_service.create_customer(
                tenant_id=tenant_id,
                email=customer_email,
                name=customer_name,
                metadata=metadata
            )
        
        # Create subscription
        subscription = stripe_service.create_subscription(
            tenant_id=tenant_id,
            customer_id=customer_id,
            plan_id=plan_id,
            trial_days=trial_days,
            metadata=metadata
        )
        
        return success_response(
            message=_('Subscription created successfully'),
            data=subscription.to_dict(),
            status_code=201
        )
        
    except StripeError as e:
        logger.error("Stripe error creating subscription", error=str(e))
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
        logger.error("Error creating subscription", error=str(e))
        return error_response(
            error_code='SUBSCRIPTION_CREATE_ERROR',
            message=_('Failed to create subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>', methods=['PUT'])
@require_tenant()
@require_permission('subscription:update')
@require_json()
@log_api_call('update_subscription')
def update_subscription(subscription_id):
    """Update an existing subscription."""
    try:
        data = request.get_json()
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Extract update fields
        new_plan_id = data.get('plan_id')
        cancel_at_period_end = data.get('cancel_at_period_end')
        metadata = data.get('metadata')
        
        # Validate new plan if provided
        if new_plan_id:
            new_plan = Plan.get_by_id(new_plan_id)
            if not new_plan or not new_plan.is_active:
                return validation_error_response([{
                    'field': 'plan_id',
                    'message': _('Invalid or inactive plan')
                }])
        
        # Update using Stripe service
        stripe_service = StripeService()
        updated_subscription = stripe_service.update_subscription(
            subscription_id=subscription_id,
            plan_id=new_plan_id,
            cancel_at_period_end=cancel_at_period_end,
            metadata=metadata
        )
        
        return success_response(
            message=_('Subscription updated successfully'),
            data=updated_subscription.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error updating subscription", error=str(e))
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
        logger.error("Error updating subscription", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_UPDATE_ERROR',
            message=_('Failed to update subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/cancel', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@log_api_call('cancel_subscription')
def cancel_subscription(subscription_id):
    """Cancel a subscription."""
    try:
        data = request.get_json() or {}
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        if subscription.is_canceled:
            return error_response(
                error_code='SUBSCRIPTION_STATE_ERROR',
                message=_('Subscription is already canceled'),
                status_code=400
            )
        
        # Get cancellation options
        at_period_end = data.get('at_period_end', True)
        
        # Cancel using Stripe service
        stripe_service = StripeService()
        canceled_subscription = stripe_service.cancel_subscription(
            subscription_id=subscription_id,
            at_period_end=at_period_end
        )
        
        return success_response(
            message=_('Subscription canceled successfully'),
            data=canceled_subscription.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error canceling subscription", error=str(e))
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
        logger.error("Error canceling subscription", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_CANCEL_ERROR',
            message=_('Failed to cancel subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/reactivate', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@log_api_call('reactivate_subscription')
def reactivate_subscription(subscription_id):
    """Reactivate a canceled subscription."""
    try:
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        if not subscription.cancel_at_period_end:
            return error_response(
                error_code='SUBSCRIPTION_STATE_ERROR',
                message=_('Subscription is not scheduled for cancellation'),
                status_code=400
            )
        
        # Reactivate using Stripe service
        stripe_service = StripeService()
        reactivated_subscription = stripe_service.reactivate_subscription(subscription_id)
        
        return success_response(
            message=_('Subscription reactivated successfully'),
            data=reactivated_subscription.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error reactivating subscription", error=str(e))
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
        logger.error("Error reactivating subscription", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_REACTIVATE_ERROR',
            message=_('Failed to reactivate subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/usage', methods=['GET'])
@require_tenant()
@require_permission('subscription:read')
@validate_pagination()
@log_api_call('get_subscription_usage')
def get_subscription_usage(subscription_id):
    """Get usage data for a subscription."""
    try:
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        page = g.page
        per_page = g.per_page
        
        # Get query parameters
        event_type = request.args.get('event_type')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        # Build usage query
        query = UsageEvent.query.filter_by(subscription_id=subscription_id)
        
        if event_type:
            query = query.filter(UsageEvent.event_type == event_type)
        
        if start_date:
            try:
                start = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                query = query.filter(UsageEvent.timestamp >= start.isoformat())
            except ValueError:
                return validation_error_response([{
                    'field': 'start_date',
                    'message': _('Invalid date format. Use ISO 8601 format.')
                }])
        
        if end_date:
            try:
                end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                query = query.filter(UsageEvent.timestamp <= end.isoformat())
            except ValueError:
                return validation_error_response([{
                    'field': 'end_date',
                    'message': _('Invalid date format. Use ISO 8601 format.')
                }])
        
        # Order by timestamp descending
        query = query.order_by(desc(UsageEvent.timestamp))
        
        # Execute paginated query
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Convert to dict
        usage_events = [event.to_dict() for event in pagination.items]
        
        # Get current entitlements
        entitlements = Entitlement.query.filter_by(subscription_id=subscription_id).all()
        entitlement_data = [entitlement.to_dict() for entitlement in entitlements]
        
        # Calculate usage summary
        total_usage = {}
        for event in pagination.items:
            event_type = event.event_type
            if event_type not in total_usage:
                total_usage[event_type] = 0
            total_usage[event_type] += event.quantity
        
        return paginated_response(
            items=usage_events,
            page=page,
            per_page=per_page,
            total=pagination.total,
            message=_('Usage data retrieved successfully'),
            summary={
                'entitlements': entitlement_data,
                'usage_summary': total_usage
            }
        )
        
    except Exception as e:
        logger.error("Error getting subscription usage", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_USAGE_ERROR',
            message=_('Failed to retrieve usage data'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/usage', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@require_json(['event_type'])
@log_api_call('record_usage')
def record_usage(subscription_id):
    """Record usage for a subscription."""
    try:
        data = request.get_json()
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Validate required fields
        event_type = data.get('event_type')
        quantity = data.get('quantity', 1)
        metadata = data.get('metadata', {})
        
        if not event_type:
            return validation_error_response([{
                'field': 'event_type',
                'message': _('Event type is required')
            }])
        
        # Validate quantity
        try:
            quantity = int(quantity)
            if quantity <= 0:
                return validation_error_response([{
                    'field': 'quantity',
                    'message': _('Quantity must be positive')
                }])
        except (ValueError, TypeError):
            return validation_error_response([{
                'field': 'quantity',
                'message': _('Invalid quantity format')
            }])
        
        # Record usage using Stripe service
        stripe_service = StripeService()
        success = stripe_service.record_usage(
            subscription_id=subscription_id,
            event_type=event_type,
            quantity=quantity,
            metadata=metadata
        )
        
        if success:
            return success_response(
                message=_('Usage recorded successfully'),
                data={
                    'event_type': event_type,
                    'quantity': quantity,
                    'timestamp': datetime.utcnow().isoformat()
                },
                status_code=201
            )
        else:
            return error_response(
                error_code='USAGE_RECORD_ERROR',
                message=_('Failed to record usage'),
                status_code=500
            )
        
    except ValidationError as e:
        return validation_error_response([{
            'field': 'general',
            'message': str(e)
        }])
    except Exception as e:
        logger.error("Error recording usage", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='USAGE_RECORD_ERROR',
            message=_('Failed to record usage'),
            status_code=500
        )


@billing_bp.route('/plans', methods=['GET'])
@require_tenant()
@require_permission('subscription:read')
@log_api_call('list_plans')
def list_plans():
    """List available subscription plans."""
    try:
        # Get active public plans
        plans = Plan.get_active_plans()
        
        # Convert to dict
        plans_data = [plan.to_dict() for plan in plans]
        
        return success_response(
            message=_('Plans retrieved successfully'),
            data=plans_data
        )
        
    except Exception as e:
        logger.error("Error listing plans", error=str(e))
        return error_response(
            error_code='PLANS_LIST_ERROR',
            message=_('Failed to retrieve plans'),
            status_code=500
        )


@billing_bp.route('/plans/<int:plan_id>', methods=['GET'])
@require_tenant()
@require_permission('subscription:read')
@log_api_call('get_plan')
def get_plan(plan_id):
    """Get a specific plan by ID."""
    try:
        plan = Plan.get_by_id(plan_id)
        
        if not plan or not plan.is_active or not plan.is_public:
            return not_found_response('Plan')
        
        return success_response(
            message=_('Plan retrieved successfully'),
            data=plan.to_dict()
        )
        
    except Exception as e:
        logger.error("Error getting plan", error=str(e), plan_id=plan_id)
        return error_response(
            error_code='PLAN_GET_ERROR',
            message=_('Failed to retrieve plan'),
            status_code=500
        )

@billing_bp.route('/plans', methods=['POST'])
@require_tenant()
@require_permission('plan:create')
@require_json(['name', 'price'])
@log_api_call('create_plan')
def create_plan():
    """Create a new subscription plan."""
    try:
        data = request.get_json()
        
        # Validate required fields
        name = data.get('name')
        price = data.get('price')
        
        if not name or not price:
            return validation_error_response([{
                'field': 'general',
                'message': _('Name and price are required')
            }])
        
        # Validate price
        try:
            price = Decimal(str(price))
            if price <= 0:
                return validation_error_response([{
                    'field': 'price',
                    'message': _('Price must be positive')
                }])
        except (ValueError, TypeError):
            return validation_error_response([{
                'field': 'price',
                'message': _('Invalid price format')
            }])
        
        # Optional fields
        billing_interval = data.get('billing_interval', 'month')
        features = data.get('features', {})
        limits = data.get('limits', {})
        metadata = data.get('metadata', {})
        
        # Validate billing interval
        if billing_interval not in ['month', 'year']:
            return validation_error_response([{
                'field': 'billing_interval',
                'message': _('Billing interval must be "month" or "year"')
            }])
        
        # Create plan using Stripe service
        stripe_service = StripeService()
        plan = stripe_service.create_plan(
            name=name,
            price=price,
            billing_interval=billing_interval,
            features=features,
            limits=limits,
            metadata=metadata
        )
        
        return success_response(
            message=_('Plan created successfully'),
            data=plan.to_dict(),
            status_code=201
        )
        
    except StripeError as e:
        logger.error("Stripe error creating plan", error=str(e))
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
        logger.error("Error creating plan", error=str(e))
        return error_response(
            error_code='PLAN_CREATE_ERROR',
            message=_('Failed to create plan'),
            status_code=500
        )


@billing_bp.route('/plans/<int:plan_id>', methods=['PUT'])
@require_tenant()
@require_permission('plan:update')
@require_json()
@log_api_call('update_plan')
def update_plan(plan_id):
    """Update an existing plan."""
    try:
        data = request.get_json()
        
        # Extract update fields
        name = data.get('name')
        features = data.get('features')
        limits = data.get('limits')
        is_active = data.get('is_active')
        metadata = data.get('metadata')
        
        # Update plan using Stripe service
        stripe_service = StripeService()
        updated_plan = stripe_service.update_plan(
            plan_id=plan_id,
            name=name,
            features=features,
            limits=limits,
            is_active=is_active,
            metadata=metadata
        )
        
        return success_response(
            message=_('Plan updated successfully'),
            data=updated_plan.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error updating plan", error=str(e))
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
        logger.error("Error updating plan", error=str(e), plan_id=plan_id)
        return error_response(
            error_code='PLAN_UPDATE_ERROR',
            message=_('Failed to update plan'),
            status_code=500
        )


@billing_bp.route('/subscriptions/trial', methods=['POST'])
@require_tenant()
@require_permission('subscription:create')
@require_json(['plan_id', 'customer_email'])
@log_api_call('create_trial_subscription')
def create_trial_subscription():
    """Create a trial subscription."""
    try:
        data = request.get_json()
        tenant_id = g.tenant_id
        
        # Validate required fields
        plan_id = data.get('plan_id')
        customer_email = data.get('customer_email')
        
        if not plan_id or not customer_email:
            return validation_error_response([{
                'field': 'general',
                'message': _('Plan ID and customer email are required')
            }])
        
        # Validate plan
        plan = Plan.get_by_id(plan_id)
        if not plan or not plan.is_active:
            return validation_error_response([{
                'field': 'plan_id',
                'message': _('Invalid or inactive plan')
            }])
        
        # Optional fields
        customer_name = data.get('customer_name')
        trial_days = data.get('trial_days', 3)  # Default 3-day trial
        metadata = data.get('metadata', {})
        
        # Validate trial days
        try:
            trial_days = int(trial_days)
            if trial_days <= 0 or trial_days > 30:
                return validation_error_response([{
                    'field': 'trial_days',
                    'message': _('Trial days must be between 1 and 30')
                }])
        except (ValueError, TypeError):
            return validation_error_response([{
                'field': 'trial_days',
                'message': _('Invalid trial days format')
            }])
        
        # Create Stripe service
        stripe_service = StripeService()
        
        # Create or get customer
        customer_id = data.get('customer_id')
        if not customer_id:
            customer_id = stripe_service.create_customer(
                tenant_id=tenant_id,
                email=customer_email,
                name=customer_name,
                metadata=metadata
            )
        
        # Create trial subscription
        subscription = stripe_service.create_trial_subscription(
            tenant_id=tenant_id,
            customer_id=customer_id,
            plan_id=plan_id,
            trial_days=trial_days,
            metadata=metadata
        )
        
        return success_response(
            message=_('Trial subscription created successfully'),
            data=subscription.to_dict(),
            status_code=201
        )
        
    except StripeError as e:
        logger.error("Stripe error creating trial subscription", error=str(e))
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
        logger.error("Error creating trial subscription", error=str(e))
        return error_response(
            error_code='TRIAL_SUBSCRIPTION_CREATE_ERROR',
            message=_('Failed to create trial subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/upgrade', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@require_json(['new_plan_id'])
@log_api_call('upgrade_subscription')
def upgrade_subscription(subscription_id):
    """Upgrade subscription to a higher plan."""
    try:
        data = request.get_json()
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Validate new plan
        new_plan_id = data.get('new_plan_id')
        new_plan = Plan.get_by_id(new_plan_id)
        if not new_plan or not new_plan.is_active:
            return validation_error_response([{
                'field': 'new_plan_id',
                'message': _('Invalid or inactive plan')
            }])
        
        # Check if it's actually an upgrade (higher price)
        current_plan = subscription.plan
        if current_plan and new_plan.get_monthly_price() <= current_plan.get_monthly_price():
            return validation_error_response([{
                'field': 'new_plan_id',
                'message': _('New plan must be higher tier than current plan')
            }])
        
        # Optional fields
        prorate = data.get('prorate', True)
        
        # Upgrade using Stripe service
        stripe_service = StripeService()
        upgraded_subscription = stripe_service.upgrade_subscription(
            subscription_id=subscription_id,
            new_plan_id=new_plan_id,
            prorate=prorate
        )
        
        return success_response(
            message=_('Subscription upgraded successfully'),
            data=upgraded_subscription.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error upgrading subscription", error=str(e))
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
        logger.error("Error upgrading subscription", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_UPGRADE_ERROR',
            message=_('Failed to upgrade subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/downgrade', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@require_json(['new_plan_id'])
@log_api_call('downgrade_subscription')
def downgrade_subscription(subscription_id):
    """Downgrade subscription to a lower plan."""
    try:
        data = request.get_json()
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Validate new plan
        new_plan_id = data.get('new_plan_id')
        new_plan = Plan.get_by_id(new_plan_id)
        if not new_plan or not new_plan.is_active:
            return validation_error_response([{
                'field': 'new_plan_id',
                'message': _('Invalid or inactive plan')
            }])
        
        # Check if it's actually a downgrade (lower price)
        current_plan = subscription.plan
        if current_plan and new_plan.get_monthly_price() >= current_plan.get_monthly_price():
            return validation_error_response([{
                'field': 'new_plan_id',
                'message': _('New plan must be lower tier than current plan')
            }])
        
        # Optional fields
        at_period_end = data.get('at_period_end', True)
        
        # Downgrade using Stripe service
        stripe_service = StripeService()
        downgraded_subscription = stripe_service.downgrade_subscription(
            subscription_id=subscription_id,
            new_plan_id=new_plan_id,
            at_period_end=at_period_end
        )
        
        return success_response(
            message=_('Subscription downgraded successfully'),
            data=downgraded_subscription.to_dict()
        )
        
    except StripeError as e:
        logger.error("Stripe error downgrading subscription", error=str(e))
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
        logger.error("Error downgrading subscription", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_DOWNGRADE_ERROR',
            message=_('Failed to downgrade subscription'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/trial/expire', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@log_api_call('expire_trial')
def expire_trial(subscription_id):
    """Manually expire a trial subscription."""
    try:
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        if not subscription.is_trial:
            return error_response(
                error_code='SUBSCRIPTION_STATE_ERROR',
                message=_('Subscription is not in trial'),
                status_code=400
            )
        
        # Expire trial using Stripe service
        stripe_service = StripeService()
        success = stripe_service.handle_trial_expiration(subscription_id)
        
        if success:
            return success_response(
                message=_('Trial expired successfully'),
                data=subscription.to_dict()
            )
        else:
            return error_response(
                error_code='TRIAL_EXPIRATION_ERROR',
                message=_('Failed to expire trial'),
                status_code=500
            )
        
    except ValidationError as e:
        return error_response(
            error_code='VALIDATION_ERROR',
            message=str(e),
            status_code=400
        )
    except Exception as e:
        logger.error("Error expiring trial", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='TRIAL_EXPIRATION_ERROR',
            message=_('Failed to expire trial'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/overage', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@require_json(['feature', 'current_usage'])
@log_api_call('handle_overage')
def handle_usage_overage(subscription_id):
    """Handle usage overage for a subscription."""
    try:
        data = request.get_json()
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Validate required fields
        feature = data.get('feature')
        current_usage = data.get('current_usage')
        
        if not feature or current_usage is None:
            return validation_error_response([{
                'field': 'general',
                'message': _('Feature and current usage are required')
            }])
        
        # Validate current usage
        try:
            current_usage = int(current_usage)
            if current_usage < 0:
                return validation_error_response([{
                    'field': 'current_usage',
                    'message': _('Current usage must be non-negative')
                }])
        except (ValueError, TypeError):
            return validation_error_response([{
                'field': 'current_usage',
                'message': _('Invalid current usage format')
            }])
        
        # Get subscription limit
        limit = subscription.get_limit(feature)
        if limit is None:
            return validation_error_response([{
                'field': 'feature',
                'message': _('Feature not found in subscription plan')
            }])
        
        if limit == -1:  # Unlimited
            return success_response(
                message=_('Feature has unlimited usage'),
                data={'overage': False, 'limit': -1, 'current_usage': current_usage}
            )
        
        # Handle overage using Stripe service
        stripe_service = StripeService()
        success = stripe_service.handle_usage_overage(
            subscription_id=subscription_id,
            feature=feature,
            current_usage=current_usage,
            limit=limit
        )
        
        overage_amount = max(0, current_usage - limit)
        
        if success:
            return success_response(
                message=_('Usage overage handled successfully'),
                data={
                    'overage': overage_amount > 0,
                    'limit': limit,
                    'current_usage': current_usage,
                    'overage_amount': overage_amount
                }
            )
        else:
            return error_response(
                error_code='OVERAGE_HANDLING_ERROR',
                message=_('Failed to handle usage overage'),
                status_code=500
            )
        
    except ValidationError as e:
        return validation_error_response([{
            'field': 'general',
            'message': str(e)
        }])
    except Exception as e:
        logger.error("Error handling usage overage", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='OVERAGE_HANDLING_ERROR',
            message=_('Failed to handle usage overage'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/quota-enforcement', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@log_api_call('enforce_quotas')
def enforce_subscription_quotas(subscription_id):
    """Enforce usage quotas for a subscription."""
    try:
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        # Use subscription service for quota enforcement
        from app.services.subscription_service import SubscriptionService
        subscription_service = SubscriptionService()
        
        result = subscription_service.enforce_usage_quotas(subscription.tenant_id)
        
        return success_response(
            message=_('Quota enforcement completed'),
            data=result
        )
        
    except ValidationError as e:
        return validation_error_response([{
            'field': 'general',
            'message': str(e)
        }])
    except Exception as e:
        logger.error("Error enforcing quotas", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='QUOTA_ENFORCEMENT_ERROR',
            message=_('Failed to enforce quotas'),
            status_code=500
        )


@billing_bp.route('/subscriptions/<int:subscription_id>/transition', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@require_json(['transition_type'])
@log_api_call('subscription_transition')
def handle_subscription_transition(subscription_id):
    """Handle subscription transitions (trial to paid, plan changes, etc.)."""
    try:
        data = request.get_json()
        
        # Check if subscription exists and belongs to tenant
        subscription = Subscription.query.filter_by(
            id=subscription_id,
            tenant_id=g.tenant_id
        ).first()
        
        if not subscription:
            return not_found_response('Subscription')
        
        transition_type = data.get('transition_type')
        
        # Use subscription service for transitions
        from app.services.subscription_service import SubscriptionService
        subscription_service = SubscriptionService()
        
        if transition_type == 'trial_to_paid':
            result = subscription_service.handle_trial_expiration(subscription_id)
        elif transition_type == 'plan_upgrade':
            new_plan_id = data.get('new_plan_id')
            if not new_plan_id:
                return validation_error_response([{
                    'field': 'new_plan_id',
                    'message': _('New plan ID is required for upgrade')
                }])
            result = subscription_service.upgrade_subscription(
                subscription_id, 
                new_plan_id, 
                prorate=data.get('prorate', True)
            )
        else:
            return validation_error_response([{
                'field': 'transition_type',
                'message': _('Invalid transition type')
            }])
        
        return success_response(
            message=_('Subscription transition completed'),
            data=result
        )
        
    except ValidationError as e:
        return validation_error_response([{
            'field': 'general',
            'message': str(e)
        }])
    except Exception as e:
        logger.error("Error handling subscription transition", error=str(e), subscription_id=subscription_id)
        return error_response(
            error_code='SUBSCRIPTION_TRANSITION_ERROR',
            message=_('Failed to handle subscription transition'),
            status_code=500
        )


@billing_bp.route('/subscriptions/bulk-operations', methods=['POST'])
@require_tenant()
@require_permission('subscription:update')
@require_json(['operation', 'subscription_ids'])
@log_api_call('bulk_subscription_operations')
def bulk_subscription_operations():
    """Handle bulk operations on subscriptions."""
    try:
        data = request.get_json()
        operation = data.get('operation')
        subscription_ids = data.get('subscription_ids', [])
        
        if not subscription_ids:
            return validation_error_response([{
                'field': 'subscription_ids',
                'message': _('At least one subscription ID is required')
            }])
        
        # Validate subscription IDs belong to tenant
        subscriptions = Subscription.query.filter(
            Subscription.id.in_(subscription_ids),
            Subscription.tenant_id == g.tenant_id
        ).all()
        
        if len(subscriptions) != len(subscription_ids):
            return validation_error_response([{
                'field': 'subscription_ids',
                'message': _('Some subscription IDs are invalid or not accessible')
            }])
        
        results = []
        
        if operation == 'enforce_quotas':
            from app.services.subscription_service import SubscriptionService
            subscription_service = SubscriptionService()
            
            for subscription in subscriptions:
                try:
                    result = subscription_service.enforce_usage_quotas(subscription.tenant_id)
                    results.append({
                        'subscription_id': subscription.id,
                        'success': True,
                        'result': result
                    })
                except Exception as e:
                    results.append({
                        'subscription_id': subscription.id,
                        'success': False,
                        'error': str(e)
                    })
        
        elif operation == 'sync_from_stripe':
            stripe_service = StripeService()
            
            for subscription in subscriptions:
                try:
                    if subscription.stripe_subscription_id:
                        synced = stripe_service.sync_subscription_from_stripe(
                            subscription.stripe_subscription_id
                        )
                        results.append({
                            'subscription_id': subscription.id,
                            'success': True,
                            'synced': synced is not None
                        })
                    else:
                        results.append({
                            'subscription_id': subscription.id,
                            'success': False,
                            'error': 'No Stripe subscription ID'
                        })
                except Exception as e:
                    results.append({
                        'subscription_id': subscription.id,
                        'success': False,
                        'error': str(e)
                    })
        
        else:
            return validation_error_response([{
                'field': 'operation',
                'message': _('Invalid operation type')
            }])
        
        success_count = sum(1 for r in results if r['success'])
        
        return success_response(
            message=_('Bulk operation completed'),
            data={
                'operation': operation,
                'total_processed': len(results),
                'successful': success_count,
                'failed': len(results) - success_count,
                'results': results
            }
        )
        
    except ValidationError as e:
        return validation_error_response([{
            'field': 'general',
            'message': str(e)
        }])
    except Exception as e:
        logger.error("Error in bulk subscription operations", error=str(e))
        return error_response(
            error_code='BULK_OPERATION_ERROR',
            message=_('Failed to perform bulk operation'),
            status_code=500
        )