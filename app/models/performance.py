"""Performance monitoring models."""
from datetime import datetime, timedelta
from sqlalchemy import Index, func, case
from app.models.base import BaseModel
from app import db


class PerformanceMetric(BaseModel):
    """Model for storing request performance metrics."""
    
    __tablename__ = 'performance_metrics'
    
    # Request information
    endpoint = db.Column(db.String(255), nullable=False, index=True)
    method = db.Column(db.String(10), nullable=False)
    status_code = db.Column(db.Integer, nullable=False, index=True)
    
    # Performance metrics
    response_time_ms = db.Column(db.Float, nullable=False, index=True)
    db_query_time_ms = db.Column(db.Float, default=0.0)
    db_query_count = db.Column(db.Integer, default=0)
    cache_hits = db.Column(db.Integer, default=0)
    cache_misses = db.Column(db.Integer, default=0)
    
    # Request details
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    ip_address = db.Column(db.String(45), nullable=True)  # IPv6 compatible
    user_agent = db.Column(db.Text, nullable=True)
    
    # Timing information
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Additional metadata
    memory_usage_mb = db.Column(db.Float, nullable=True)
    cpu_usage_percent = db.Column(db.Float, nullable=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_performance_endpoint_time', 'endpoint', 'timestamp'),
        Index('idx_performance_slow_requests', 'response_time_ms', 'timestamp'),
        Index('idx_performance_errors', 'status_code', 'timestamp'),
        Index('idx_performance_user_metrics', 'user_id', 'timestamp'),
    )
    
    @classmethod
    def log_request(cls, endpoint, method, status_code, response_time_ms, **kwargs):
        """Log a request performance metric."""
        metric = cls(
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            **kwargs
        )
        db.session.add(metric)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    @classmethod
    def get_slow_requests(cls, threshold_ms=2000, hours=24):
        """Get slow requests within the specified time period."""
        since = datetime.utcnow() - timedelta(hours=hours)
        return cls.query.filter(
            cls.response_time_ms >= threshold_ms,
            cls.timestamp >= since
        ).order_by(cls.response_time_ms.desc()).all()
    
    @classmethod
    def get_endpoint_stats(cls, endpoint, hours=24):
        """Get performance statistics for a specific endpoint."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        stats = db.session.query(
            func.count(cls.id).label('request_count'),
            func.avg(cls.response_time_ms).label('avg_response_time'),
            func.min(cls.response_time_ms).label('min_response_time'),
            func.max(cls.response_time_ms).label('max_response_time'),
            func.percentile_cont(0.95).within_group(cls.response_time_ms).label('p95_response_time'),
            func.sum(func.case([(cls.status_code >= 400, 1)], else_=0)).label('error_count')
        ).filter(
            cls.endpoint == endpoint,
            cls.timestamp >= since
        ).first()
        
        return {
            'request_count': stats.request_count or 0,
            'avg_response_time': float(stats.avg_response_time or 0),
            'min_response_time': float(stats.min_response_time or 0),
            'max_response_time': float(stats.max_response_time or 0),
            'p95_response_time': float(stats.p95_response_time or 0),
            'error_count': stats.error_count or 0,
            'error_rate': (stats.error_count or 0) / max(stats.request_count or 1, 1)
        }
    
    @classmethod
    def cleanup_old_metrics(cls, retention_days=30):
        """Clean up old performance metrics."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        deleted_count = cls.query.filter(cls.timestamp < cutoff_date).delete()
        db.session.commit()
        return deleted_count


class SlowQuery(BaseModel):
    """Model for storing slow database queries."""
    
    __tablename__ = 'slow_queries'
    
    # Query information
    query_hash = db.Column(db.String(64), nullable=False, index=True)  # MD5 hash of normalized query
    query_text = db.Column(db.Text, nullable=False)
    normalized_query = db.Column(db.Text, nullable=False)  # Query with parameters replaced
    
    # Performance metrics
    execution_time_ms = db.Column(db.Float, nullable=False, index=True)
    rows_examined = db.Column(db.Integer, nullable=True)
    rows_returned = db.Column(db.Integer, nullable=True)
    
    # Context information
    endpoint = db.Column(db.String(255), nullable=True, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=True, index=True)
    
    # Timing information
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # Additional metadata
    database_name = db.Column(db.String(100), nullable=True)
    table_names = db.Column(db.JSON, nullable=True)  # List of tables involved
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_slow_query_hash_time', 'query_hash', 'timestamp'),
        Index('idx_slow_query_execution_time', 'execution_time_ms', 'timestamp'),
        Index('idx_slow_query_endpoint', 'endpoint', 'timestamp'),
    )
    
    @classmethod
    def log_slow_query(cls, query_text, execution_time_ms, **kwargs):
        """Log a slow query."""
        import hashlib
        
        # Normalize query for hashing (remove parameters, extra whitespace)
        normalized = cls._normalize_query(query_text)
        query_hash = hashlib.md5(normalized.encode()).hexdigest()
        
        slow_query = cls(
            query_hash=query_hash,
            query_text=query_text,
            normalized_query=normalized,
            execution_time_ms=execution_time_ms,
            **kwargs
        )
        db.session.add(slow_query)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    @classmethod
    def _normalize_query(cls, query_text):
        """Normalize query text for consistent hashing."""
        import re
        
        # Remove extra whitespace
        normalized = re.sub(r'\s+', ' ', query_text.strip())
        
        # Replace parameter placeholders with generic markers
        normalized = re.sub(r'%\([^)]+\)s', '?', normalized)  # SQLAlchemy parameters
        normalized = re.sub(r'\$\d+', '?', normalized)  # PostgreSQL parameters
        normalized = re.sub(r'\?', '?', normalized)  # Generic parameters
        
        # Replace string literals with placeholders
        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r'"[^"]*"', '"?"', normalized)
        
        # Replace numeric literals with placeholders
        normalized = re.sub(r'\b\d+\b', '?', normalized)
        
        return normalized.upper()
    
    @classmethod
    def get_frequent_slow_queries(cls, hours=24, limit=10):
        """Get most frequent slow queries."""
        since = datetime.utcnow() - timedelta(hours=hours)
        
        return db.session.query(
            cls.query_hash,
            cls.normalized_query,
            func.count(cls.id).label('occurrence_count'),
            func.avg(cls.execution_time_ms).label('avg_execution_time'),
            func.max(cls.execution_time_ms).label('max_execution_time')
        ).filter(
            cls.timestamp >= since
        ).group_by(
            cls.query_hash, cls.normalized_query
        ).order_by(
            func.count(cls.id).desc()
        ).limit(limit).all()


class ServiceHealth(BaseModel):
    """Model for storing service health status."""
    
    __tablename__ = 'service_health'
    
    # Service information
    service_name = db.Column(db.String(100), nullable=False, index=True)
    service_type = db.Column(db.String(50), nullable=False)  # database, cache, external_api, etc.
    endpoint_url = db.Column(db.String(500), nullable=True)
    
    # Health status
    status = db.Column(db.String(20), nullable=False, index=True)  # healthy, degraded, unavailable
    response_time_ms = db.Column(db.Float, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
    
    # Check information
    check_type = db.Column(db.String(50), nullable=False)  # ping, query, api_call, etc.
    last_check = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    next_check = db.Column(db.DateTime, nullable=True, index=True)
    
    # Additional metadata
    version = db.Column(db.String(50), nullable=True)
    extra_metadata = db.Column(db.JSON, nullable=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_service_health_name_status', 'service_name', 'status'),
        Index('idx_service_health_last_check', 'last_check'),
        Index('idx_service_health_next_check', 'next_check'),
    )
    
    @classmethod
    def update_service_status(cls, service_name, service_type, status, **kwargs):
        """Update or create service health status."""
        service = cls.query.filter_by(
            service_name=service_name,
            service_type=service_type
        ).first()
        
        if service:
            service.status = status
            service.last_check = datetime.utcnow()
            for key, value in kwargs.items():
                if hasattr(service, key):
                    setattr(service, key, value)
        else:
            service = cls(
                service_name=service_name,
                service_type=service_type,
                status=status,
                **kwargs
            )
            db.session.add(service)
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        return service
    
    @classmethod
    def get_unhealthy_services(cls):
        """Get all services that are not healthy."""
        return cls.query.filter(cls.status != 'healthy').all()
    
    @classmethod
    def get_service_status_summary(cls):
        """Get summary of all service statuses."""
        return db.session.query(
            cls.status,
            func.count(cls.id).label('count')
        ).group_by(cls.status).all()


class PerformanceAlert(BaseModel):
    """Model for storing performance alerts."""
    
    __tablename__ = 'performance_alerts'
    
    # Alert information
    alert_type = db.Column(db.String(50), nullable=False, index=True)  # slow_request, high_error_rate, etc.
    severity = db.Column(db.String(20), nullable=False, index=True)  # low, medium, high, critical
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    
    # Alert context
    endpoint = db.Column(db.String(255), nullable=True, index=True)
    service_name = db.Column(db.String(100), nullable=True, index=True)
    metric_value = db.Column(db.Float, nullable=True)
    threshold_value = db.Column(db.Float, nullable=True)
    
    # Alert status
    status = db.Column(db.String(20), default='active', nullable=False, index=True)  # active, acknowledged, resolved
    acknowledged_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    
    # Timing information
    first_occurrence = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    last_occurrence = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    occurrence_count = db.Column(db.Integer, default=1, nullable=False)
    
    # Additional metadata
    alert_metadata = db.Column(db.JSON, nullable=True)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_performance_alert_type_status', 'alert_type', 'status'),
        Index('idx_performance_alert_severity', 'severity', 'first_occurrence'),
        Index('idx_performance_alert_endpoint', 'endpoint', 'status'),
    )
    
    @classmethod
    def create_or_update_alert(cls, alert_type, severity, title, description, **kwargs):
        """Create a new alert or update existing one."""
        # Check for existing active alert of the same type
        existing = cls.query.filter_by(
            alert_type=alert_type,
            status='active',
            endpoint=kwargs.get('endpoint'),
            service_name=kwargs.get('service_name')
        ).first()
        
        if existing:
            # Update existing alert
            existing.last_occurrence = datetime.utcnow()
            existing.occurrence_count += 1
            existing.metric_value = kwargs.get('metric_value', existing.metric_value)
            if kwargs.get('alert_metadata'):
                existing.alert_metadata = kwargs['alert_metadata']
        else:
            # Create new alert
            alert = cls(
                alert_type=alert_type,
                severity=severity,
                title=title,
                description=description,
                **kwargs
            )
            db.session.add(alert)
            existing = alert
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
        
        return existing
    
    @classmethod
    def get_active_alerts(cls, severity=None):
        """Get active alerts, optionally filtered by severity."""
        query = cls.query.filter_by(status='active')
        if severity:
            query = query.filter_by(severity=severity)
        return query.order_by(cls.first_occurrence.desc()).all()
    
    @classmethod
    def acknowledge_alert(cls, alert_id, user_id):
        """Acknowledge an alert."""
        alert = cls.query.get(alert_id)
        if alert and alert.status == 'active':
            alert.status = 'acknowledged'
            alert.acknowledged_by = user_id
            alert.acknowledged_at = datetime.utcnow()
            db.session.commit()
        return alert
    
    @classmethod
    def resolve_alert(cls, alert_id):
        """Resolve an alert."""
        alert = cls.query.get(alert_id)
        if alert and alert.status in ['active', 'acknowledged']:
            alert.status = 'resolved'
            alert.resolved_at = datetime.utcnow()
            db.session.commit()
        return alert