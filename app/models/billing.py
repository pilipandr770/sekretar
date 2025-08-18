"""Billing and subscription models."""
from sqlalchemy import Column, String, Text, Integer, ForeignKey, Boolean, JSON, Numeric, DateTime
from sqlalchemy.orm import relationship
from app.models.base import TenantAwareModel, SoftDeleteMixin, AuditMixin, BaseModel, get_fk_reference


class Plan(BaseModel, SoftDeleteMixin):
    """Subscription plan model."""
    
    __tablename__ = 'plans'
    
    # Basic information
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    
    # Pricing
    price = Column(Numeric(10, 2), nullable=False)  # Monthly price
    billing_interval = Column(String(20), default='month', nullable=False)  # month, year
    
    # Features and limits (JSON configuration)
    features = Column(JSON, default=dict, nullable=False)
    limits = Column(JSON, default=dict, nullable=False)
    
    # Status
    is_active = Column(Boolean, default=True, nullable=False)
    is_public = Column(Boolean, default=True, nullable=False)  # Visible to customers
    
    # Stripe integration
    stripe_price_id = Column(String(255), nullable=True, index=True)
    stripe_product_id = Column(String(255), nullable=True)
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    subscriptions = relationship('Subscription', back_populates='plan')
    
    def __repr__(self):
        return f'<Plan {self.name}>'
    
    def get_feature(self, feature_name, default=None):
        """Get feature configuration."""
        return self.features.get(feature_name, default) if self.features else default
    
    def set_feature(self, feature_name, value):
        """Set feature configuration."""
        if self.features is None:
            self.features = {}
        self.features[feature_name] = value
        return self
    
    def get_limit(self, limit_name, default=None):
        """Get limit value."""
        return self.limits.get(limit_name, default) if self.limits else default
    
    def set_limit(self, limit_name, value):
        """Set limit value."""
        if self.limits is None:
            self.limits = {}
        self.limits[limit_name] = value
        return self
    
    def has_feature(self, feature_name):
        """Check if plan has a specific feature."""
        return self.get_feature(feature_name, False)
    
    def get_monthly_price(self):
        """Get monthly price (convert from yearly if needed)."""
        if self.billing_interval == 'year':
            return float(self.price) / 12
        return float(self.price)
    
    def get_yearly_price(self):
        """Get yearly price (convert from monthly if needed)."""
        if self.billing_interval == 'month':
            return float(self.price) * 12
        return float(self.price)
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['monthly_price'] = self.get_monthly_price()
        data['yearly_price'] = self.get_yearly_price()
        data['subscription_count'] = len(self.subscriptions) if self.subscriptions else 0
        
        return data
    
    @classmethod
    def get_active_plans(cls):
        """Get active public plans."""
        return cls.query.filter_by(is_active=True, is_public=True).all()
    
    @classmethod
    def get_by_stripe_price_id(cls, stripe_price_id):
        """Get plan by Stripe price ID."""
        return cls.query.filter_by(stripe_price_id=stripe_price_id).first()
    
    @classmethod
    def create_default_plans(cls):
        """Create default subscription plans."""
        plans = [
            {
                'name': 'Starter',
                'description': 'Perfect for small businesses getting started',
                'price': 29.00,
                'features': {
                    'channels': ['telegram', 'signal', 'widget'],
                    'ai_responses': True,
                    'crm': True,
                    'calendar': True,
                    'knowledge_base': True,
                    'basic_analytics': True
                },
                'limits': {
                    'users': 3,
                    'messages_per_month': 1000,
                    'knowledge_documents': 50,
                    'leads': 500
                }
            },
            {
                'name': 'Pro',
                'description': 'Advanced features for growing businesses',
                'price': 79.00,
                'features': {
                    'channels': ['telegram', 'signal', 'widget', 'email'],
                    'ai_responses': True,
                    'crm': True,
                    'calendar': True,
                    'knowledge_base': True,
                    'advanced_analytics': True,
                    'kyb_monitoring': True,
                    'custom_integrations': True
                },
                'limits': {
                    'users': 10,
                    'messages_per_month': 5000,
                    'knowledge_documents': 200,
                    'leads': 2000
                }
            },
            {
                'name': 'Team',
                'description': 'Collaboration features for larger teams',
                'price': 149.00,
                'features': {
                    'channels': ['telegram', 'signal', 'widget', 'email', 'phone'],
                    'ai_responses': True,
                    'crm': True,
                    'calendar': True,
                    'knowledge_base': True,
                    'advanced_analytics': True,
                    'kyb_monitoring': True,
                    'custom_integrations': True,
                    'team_collaboration': True,
                    'advanced_permissions': True
                },
                'limits': {
                    'users': 25,
                    'messages_per_month': 15000,
                    'knowledge_documents': 500,
                    'leads': 5000
                }
            },
            {
                'name': 'Enterprise',
                'description': 'Custom solutions for large organizations',
                'price': 299.00,
                'features': {
                    'channels': ['telegram', 'signal', 'widget', 'email', 'phone', 'custom'],
                    'ai_responses': True,
                    'crm': True,
                    'calendar': True,
                    'knowledge_base': True,
                    'advanced_analytics': True,
                    'kyb_monitoring': True,
                    'custom_integrations': True,
                    'team_collaboration': True,
                    'advanced_permissions': True,
                    'white_label': True,
                    'dedicated_support': True
                },
                'limits': {
                    'users': -1,  # Unlimited
                    'messages_per_month': -1,  # Unlimited
                    'knowledge_documents': -1,  # Unlimited
                    'leads': -1  # Unlimited
                }
            }
        ]
        
        created_plans = []
        for plan_data in plans:
            plan = cls.create(**plan_data)
            created_plans.append(plan)
        
        return created_plans


class Subscription(TenantAwareModel, SoftDeleteMixin, AuditMixin):
    """Subscription model."""
    
    __tablename__ = 'subscriptions'
    
    # Plan relationship
    plan_id = Column(Integer, ForeignKey(get_fk_reference('plans')), nullable=False, index=True)
    plan = relationship('Plan', back_populates='subscriptions')
    
    # Stripe integration
    stripe_subscription_id = Column(String(255), nullable=True, unique=True, index=True)
    stripe_customer_id = Column(String(255), nullable=True, index=True)
    
    # Status
    status = Column(String(50), default='active', nullable=False, index=True)  # active, canceled, past_due, unpaid, trialing
    
    # Billing periods
    current_period_start = Column(String(50), nullable=True)  # ISO datetime string
    current_period_end = Column(String(50), nullable=True)  # ISO datetime string
    
    # Trial information
    trial_start = Column(String(50), nullable=True)
    trial_end = Column(String(50), nullable=True)
    
    # Cancellation
    canceled_at = Column(String(50), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    usage_events = relationship('UsageEvent', back_populates='subscription', cascade='all, delete-orphan')
    entitlements = relationship('Entitlement', back_populates='subscription', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<Subscription {self.plan.name} for tenant {self.tenant_id}>'
    
    @property
    def is_active(self):
        """Check if subscription is active."""
        return self.status in ['active', 'trialing']
    
    @property
    def is_trial(self):
        """Check if subscription is in trial."""
        return self.status == 'trialing'
    
    @property
    def is_canceled(self):
        """Check if subscription is canceled."""
        return self.status == 'canceled'
    
    @property
    def is_past_due(self):
        """Check if subscription is past due."""
        return self.status == 'past_due'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.extra_data.get(key, default) if self.extra_data else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
        return self
    
    def cancel(self, at_period_end=True):
        """Cancel subscription."""
        if at_period_end:
            self.cancel_at_period_end = True
        else:
            from datetime import datetime
            self.status = 'canceled'
            self.canceled_at = datetime.utcnow().isoformat()
        return self
    
    def reactivate(self):
        """Reactivate canceled subscription."""
        if self.is_canceled:
            self.status = 'active'
            self.canceled_at = None
            self.cancel_at_period_end = False
        return self
    
    def has_feature(self, feature_name):
        """Check if subscription has a specific feature."""
        return self.plan.has_feature(feature_name) if self.plan else False
    
    def get_limit(self, limit_name):
        """Get subscription limit."""
        return self.plan.get_limit(limit_name) if self.plan else None
    
    def is_within_limit(self, limit_name, current_usage):
        """Check if current usage is within limit."""
        limit = self.get_limit(limit_name)
        if limit is None or limit == -1:  # No limit or unlimited
            return True
        return current_usage <= limit
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['is_active'] = self.is_active
        data['is_trial'] = self.is_trial
        data['is_canceled'] = self.is_canceled
        data['is_past_due'] = self.is_past_due
        
        # Add plan info
        if self.plan:
            data['plan_name'] = self.plan.name
            data['plan_price'] = float(self.plan.price)
            data['plan_features'] = self.plan.features
            data['plan_limits'] = self.plan.limits
        
        return data
    
    @classmethod
    def get_by_stripe_id(cls, stripe_subscription_id):
        """Get subscription by Stripe ID."""
        return cls.query.filter_by(stripe_subscription_id=stripe_subscription_id).first()
    
    @classmethod
    def get_active_subscriptions(cls, tenant_id=None):
        """Get active subscriptions."""
        query = cls.query.filter(cls.status.in_(['active', 'trialing']))
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        return query.all()


class UsageEvent(TenantAwareModel):
    """Usage event model for metering."""
    
    __tablename__ = 'usage_events'
    
    # Subscription relationship
    subscription_id = Column(Integer, ForeignKey(get_fk_reference('subscriptions')), nullable=False, index=True)
    subscription = relationship('Subscription', back_populates='usage_events')
    
    # Event information
    event_type = Column(String(100), nullable=False, index=True)  # message_sent, document_processed, etc.
    quantity = Column(Integer, default=1, nullable=False)
    
    # Timestamp
    timestamp = Column(String(50), nullable=False, index=True)  # ISO datetime string
    
    # Metadata
    event_metadata = Column(JSON, default=dict, nullable=False)
    
    def __repr__(self):
        return f'<UsageEvent {self.event_type} x{self.quantity}>'
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.event_metadata.get(key, default) if self.event_metadata else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.event_metadata is None:
            self.event_metadata = {}
        self.event_metadata[key] = value
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add subscription info
        if self.subscription:
            data['subscription_plan'] = self.subscription.plan.name if self.subscription.plan else None
        
        return data
    
    @classmethod
    def record_usage(cls, tenant_id, subscription_id, event_type, quantity=1, **metadata):
        """Record a usage event."""
        from datetime import datetime
        
        return cls.create(
            tenant_id=tenant_id,
            subscription_id=subscription_id,
            event_type=event_type,
            quantity=quantity,
            timestamp=datetime.utcnow().isoformat(),
            event_metadata=metadata
        )
    
    @classmethod
    def get_usage_for_period(cls, subscription_id, event_type, start_date, end_date):
        """Get usage for a specific period."""
        return cls.query.filter(
            cls.subscription_id == subscription_id,
            cls.event_type == event_type,
            cls.timestamp >= start_date,
            cls.timestamp <= end_date
        ).all()
    
    @classmethod
    def get_total_usage(cls, subscription_id, event_type, start_date=None, end_date=None):
        """Get total usage quantity for an event type."""
        query = cls.query.filter(
            cls.subscription_id == subscription_id,
            cls.event_type == event_type
        )
        
        if start_date:
            query = query.filter(cls.timestamp >= start_date)
        
        if end_date:
            query = query.filter(cls.timestamp <= end_date)
        
        events = query.all()
        return sum(event.quantity for event in events)


class Entitlement(TenantAwareModel):
    """Entitlement model for quota enforcement."""
    
    __tablename__ = 'entitlements'
    
    # Subscription relationship
    subscription_id = Column(Integer, ForeignKey(get_fk_reference('subscriptions')), nullable=False, index=True)
    subscription = relationship('Subscription', back_populates='entitlements')
    
    # Entitlement information
    feature = Column(String(100), nullable=False, index=True)  # Feature or resource name
    limit_value = Column(Integer, nullable=True)  # -1 for unlimited, None for boolean features
    used_value = Column(Integer, default=0, nullable=False)  # Current usage
    
    # Reset information
    reset_date = Column(String(50), nullable=True)  # ISO datetime string for when usage resets
    reset_frequency = Column(String(20), nullable=True)  # monthly, yearly, never
    
    def __repr__(self):
        return f'<Entitlement {self.feature} {self.used_value}/{self.limit_value}>'
    
    @property
    def is_unlimited(self):
        """Check if entitlement is unlimited."""
        return self.limit_value == -1
    
    @property
    def is_over_limit(self):
        """Check if usage is over limit."""
        if self.is_unlimited or self.limit_value is None:
            return False
        return self.used_value > self.limit_value
    
    @property
    def usage_percentage(self):
        """Get usage as percentage of limit."""
        if self.is_unlimited or self.limit_value is None or self.limit_value == 0:
            return 0.0
        return (self.used_value / self.limit_value) * 100
    
    def increment_usage(self, amount=1):
        """Increment usage."""
        self.used_value += amount
        return self
    
    def decrement_usage(self, amount=1):
        """Decrement usage."""
        self.used_value = max(0, self.used_value - amount)
        return self
    
    def reset_usage(self):
        """Reset usage to zero."""
        self.used_value = 0
        return self
    
    def can_use(self, amount=1):
        """Check if can use specified amount without exceeding limit."""
        if self.is_unlimited or self.limit_value is None:
            return True
        return (self.used_value + amount) <= self.limit_value
    
    def remaining_quota(self):
        """Get remaining quota."""
        if self.is_unlimited or self.limit_value is None:
            return -1  # Unlimited
        return max(0, self.limit_value - self.used_value)
    
    def refresh(self):
        """Refresh the object from database."""
        from app import db
        db.session.refresh(self)
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['is_unlimited'] = self.is_unlimited
        data['is_over_limit'] = self.is_over_limit
        data['usage_percentage'] = self.usage_percentage
        data['remaining_quota'] = self.remaining_quota()
        
        return data
    
    @classmethod
    def get_by_feature(cls, subscription_id, feature):
        """Get entitlement by feature."""
        return cls.query.filter_by(
            subscription_id=subscription_id,
            feature=feature
        ).first()
    
    @classmethod
    def create_from_plan(cls, tenant_id, subscription_id, plan):
        """Create entitlements from plan limits."""
        entitlements = []
        
        if plan.limits:
            for feature, limit in plan.limits.items():
                entitlement = cls.create(
                    tenant_id=tenant_id,
                    subscription_id=subscription_id,
                    feature=feature,
                    limit_value=limit,
                    reset_frequency='monthly' if feature.endswith('_per_month') else 'never'
                )
                entitlements.append(entitlement)
        
        return entitlements


class Invoice(TenantAwareModel, SoftDeleteMixin):
    """Invoice model for Stripe integration."""
    
    __tablename__ = 'invoices'
    
    # Subscription relationship
    subscription_id = Column(Integer, ForeignKey(get_fk_reference('subscriptions')), nullable=True, index=True)
    subscription = relationship('Subscription')
    
    # Stripe integration
    stripe_invoice_id = Column(String(255), nullable=True, unique=True, index=True)
    stripe_payment_intent_id = Column(String(255), nullable=True)
    
    # Invoice information
    invoice_number = Column(String(100), nullable=True)
    amount_total = Column(Numeric(10, 2), nullable=False)
    amount_paid = Column(Numeric(10, 2), default=0, nullable=False)
    currency = Column(String(3), default='USD', nullable=False)
    
    # Status
    status = Column(String(50), default='draft', nullable=False, index=True)  # draft, open, paid, void, uncollectible
    
    # Dates
    invoice_date = Column(String(50), nullable=True)  # ISO datetime string
    due_date = Column(String(50), nullable=True)
    paid_at = Column(String(50), nullable=True)
    
    # URLs
    hosted_invoice_url = Column(String(1000), nullable=True)
    invoice_pdf_url = Column(String(1000), nullable=True)
    
    # Metadata
    extra_data = Column(JSON, default=dict, nullable=False)
    
    def __repr__(self):
        return f'<Invoice {self.invoice_number or self.id}>'
    
    @property
    def is_paid(self):
        """Check if invoice is paid."""
        return self.status == 'paid'
    
    @property
    def is_overdue(self):
        """Check if invoice is overdue."""
        if self.status == 'paid' or not self.due_date:
            return False
        
        from datetime import datetime
        try:
            due = datetime.fromisoformat(self.due_date.replace('Z', '+00:00'))
            return datetime.utcnow() > due
        except (ValueError, AttributeError):
            return False
    
    @property
    def amount_due(self):
        """Get amount still due."""
        return float(self.amount_total) - float(self.amount_paid)
    
    def get_metadata(self, key, default=None):
        """Get metadata value."""
        return self.extra_data.get(key, default) if self.extra_data else default
    
    def set_metadata(self, key, value):
        """Set metadata value."""
        if self.extra_data is None:
            self.extra_data = {}
        self.extra_data[key] = value
        return self
    
    def mark_as_paid(self):
        """Mark invoice as paid."""
        from datetime import datetime
        self.status = 'paid'
        self.amount_paid = self.amount_total
        self.paid_at = datetime.utcnow().isoformat()
        return self
    
    def mark_as_void(self):
        """Mark invoice as void."""
        self.status = 'void'
        return self
    
    def to_dict(self, exclude=None):
        """Convert to dictionary."""
        exclude = exclude or []
        data = super().to_dict(exclude=exclude)
        
        # Add computed fields
        data['is_paid'] = self.is_paid
        data['is_overdue'] = self.is_overdue
        data['amount_due'] = self.amount_due
        
        # Add subscription info
        if self.subscription:
            data['subscription_plan'] = self.subscription.plan.name if self.subscription.plan else None
        
        return data
    
    @classmethod
    def get_by_stripe_id(cls, stripe_invoice_id):
        """Get invoice by Stripe ID."""
        return cls.query.filter_by(stripe_invoice_id=stripe_invoice_id).first()
    
    @classmethod
    def get_unpaid_invoices(cls, tenant_id=None):
        """Get unpaid invoices."""
        query = cls.query.filter(cls.status.in_(['open', 'past_due']))
        
        if tenant_id:
            query = query.filter_by(tenant_id=tenant_id)
        
        return query.all()
    
    @classmethod
    def get_overdue_invoices(cls, tenant_id=None):
        """Get overdue invoices."""
        invoices = cls.get_unpaid_invoices(tenant_id)
        return [invoice for invoice in invoices if invoice.is_overdue]