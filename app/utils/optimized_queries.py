"""
Optimized database queries for common operations.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy import and_, or_, func, text
from sqlalchemy.orm import joinedload, selectinload, contains_eager
from flask import current_app
from app.extensions import db
from app.utils.performance_optimizer import performance_optimizer
import structlog

logger = structlog.get_logger(__name__)


class OptimizedUserQueries:
    """Optimized queries for User model operations."""
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=300, key_prefix='user')
    def get_user_with_roles(user_id: int, tenant_id: Optional[int] = None):
        """Get user with roles preloaded."""
        from app.models.user import User
        
        query = User.query.options(
            selectinload(User.roles),
            joinedload(User.tenant)
        ).filter(
            User.id == user_id,
            User.is_active == True,
            User.deleted_at.is_(None)
        )
        
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        
        return query.first()
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=600, key_prefix='users')
    def get_tenant_users(tenant_id: int, include_inactive: bool = False):
        """Get all users for a tenant with optimized loading."""
        from app.models.user import User
        
        query = User.query.options(
            selectinload(User.roles)
        ).filter(
            User.tenant_id == tenant_id,
            User.deleted_at.is_(None)
        )
        
        if not include_inactive:
            query = query.filter(User.is_active == True)
        
        return query.order_by(User.created_at.desc()).all()
    
    @staticmethod
    def authenticate_user_optimized(email: str, password: str, tenant_id: Optional[int] = None):
        """Optimized user authentication with minimal queries."""
        from app.models.user import User
        
        # Normalize email
        email = email.strip().lower()
        
        # Single query with all needed data
        query = User.query.options(
            joinedload(User.tenant)
        ).filter(
            User.email == email,
            User.is_active == True,
            User.deleted_at.is_(None)
        )
        
        if tenant_id:
            query = query.filter(User.tenant_id == tenant_id)
        
        user = query.first()
        
        if user and user.check_password(password):
            # Update last login in background to avoid blocking
            try:
                db.session.execute(
                    text("UPDATE users SET last_login_at = :now WHERE id = :user_id"),
                    {'now': func.now(), 'user_id': user.id}
                )
                db.session.commit()
            except Exception as e:
                logger.warning("Failed to update last login", user_id=user.id, error=str(e))
                db.session.rollback()
            
            return user
        
        return None


class OptimizedCRMQueries:
    """Optimized queries for CRM operations."""
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=300, key_prefix='leads')
    def get_tenant_leads_with_details(tenant_id: int, limit: int = 50, offset: int = 0):
        """Get leads with all related data in minimal queries."""
        from app.models.lead import Lead
        
        query = Lead.query.options(
            joinedload(Lead.assigned_to),
            joinedload(Lead.contact),
            joinedload(Lead.pipeline),
            joinedload(Lead.stage),
            selectinload(Lead.tasks),
            selectinload(Lead.notes)
        ).filter(
            Lead.tenant_id == tenant_id,
            Lead.deleted_at.is_(None)
        ).order_by(Lead.updated_at.desc())
        
        if limit:
            query = query.limit(limit)
        if offset:
            query = query.offset(offset)
        
        return query.all()
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=180, key_prefix='lead_stats')
    def get_lead_statistics(tenant_id: int):
        """Get lead statistics with optimized aggregation."""
        from app.models.lead import Lead
        from app.models.pipeline import Stage
        
        # Single query for all statistics
        stats_query = db.session.query(
            func.count(Lead.id).label('total_leads'),
            func.count(func.nullif(Lead.assigned_to_id, None)).label('assigned_leads'),
            func.avg(Lead.score).label('avg_score')
        ).filter(
            Lead.tenant_id == tenant_id,
            Lead.deleted_at.is_(None)
        ).first()
        
        # Stage distribution
        stage_stats = db.session.query(
            Stage.name,
            func.count(Lead.id).label('count')
        ).join(Lead).filter(
            Lead.tenant_id == tenant_id,
            Lead.deleted_at.is_(None)
        ).group_by(Stage.name).all()
        
        return {
            'total_leads': stats_query.total_leads or 0,
            'assigned_leads': stats_query.assigned_leads or 0,
            'avg_score': float(stats_query.avg_score or 0),
            'stage_distribution': {stage.name: stage.count for stage in stage_stats}
        }


class OptimizedKnowledgeQueries:
    """Optimized queries for Knowledge Base operations."""
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=600, key_prefix='knowledge')
    def get_tenant_documents_with_chunks(tenant_id: int, limit: int = 20):
        """Get documents with chunk count in optimized way."""
        from app.models.knowledge import Document, Chunk
        
        # Use subquery to get chunk counts
        chunk_counts = db.session.query(
            Chunk.document_id,
            func.count(Chunk.id).label('chunk_count')
        ).filter(
            Chunk.tenant_id == tenant_id
        ).group_by(Chunk.document_id).subquery()
        
        query = db.session.query(Document).options(
            joinedload(Document.knowledge_source)
        ).outerjoin(
            chunk_counts, Document.id == chunk_counts.c.document_id
        ).add_columns(
            func.coalesce(chunk_counts.c.chunk_count, 0).label('chunk_count')
        ).filter(
            Document.tenant_id == tenant_id
        ).order_by(Document.updated_at.desc())
        
        if limit:
            query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def search_documents_optimized(tenant_id: int, query_text: str, limit: int = 10):
        """Optimized document search using database full-text search."""
        from app.models.knowledge import Document, Chunk
        
        # Use database-specific full-text search
        if 'postgresql' in current_app.config.get('SQLALCHEMY_DATABASE_URI', ''):
            # PostgreSQL full-text search
            search_query = db.session.query(Document).options(
                joinedload(Document.knowledge_source)
            ).filter(
                Document.tenant_id == tenant_id,
                func.to_tsvector('english', Document.content).match(query_text)
            ).order_by(
                func.ts_rank(func.to_tsvector('english', Document.content), 
                           func.plainto_tsquery('english', query_text)).desc()
            ).limit(limit)
        else:
            # SQLite fallback with LIKE search
            search_query = db.session.query(Document).options(
                joinedload(Document.knowledge_source)
            ).filter(
                Document.tenant_id == tenant_id,
                or_(
                    Document.title.ilike(f'%{query_text}%'),
                    Document.content.ilike(f'%{query_text}%')
                )
            ).order_by(Document.updated_at.desc()).limit(limit)
        
        return search_query.all()


class OptimizedBillingQueries:
    """Optimized queries for billing operations."""
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=300, key_prefix='billing')
    def get_tenant_usage_summary(tenant_id: int, days: int = 30):
        """Get usage summary for the last N days."""
        from app.models.billing import UsageEvent
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        usage_stats = db.session.query(
            UsageEvent.event_type,
            func.count(UsageEvent.id).label('count'),
            func.sum(UsageEvent.quantity).label('total_quantity')
        ).filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.created_at >= cutoff_date
        ).group_by(UsageEvent.event_type).all()
        
        return {
            stat.event_type: {
                'count': stat.count,
                'total_quantity': float(stat.total_quantity or 0)
            }
            for stat in usage_stats
        }
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=600, key_prefix='subscription')
    def get_active_subscriptions_with_usage(tenant_id: Optional[int] = None):
        """Get active subscriptions with current usage."""
        from app.models.billing import Subscription, UsageEvent
        from datetime import datetime, timedelta
        
        # Base query for active subscriptions
        query = Subscription.query.options(
            joinedload(Subscription.plan),
            joinedload(Subscription.tenant)
        ).filter(
            Subscription.status.in_(['active', 'trialing'])
        )
        
        if tenant_id:
            query = query.filter(Subscription.tenant_id == tenant_id)
        
        subscriptions = query.all()
        
        # Get usage for current billing period
        current_month_start = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        for subscription in subscriptions:
            usage_stats = db.session.query(
                func.count(UsageEvent.id).label('total_events'),
                func.sum(UsageEvent.quantity).label('total_quantity')
            ).filter(
                UsageEvent.subscription_id == subscription.id,
                UsageEvent.created_at >= current_month_start
            ).first()
            
            subscription.current_usage = {
                'total_events': usage_stats.total_events or 0,
                'total_quantity': float(usage_stats.total_quantity or 0)
            }
        
        return subscriptions


class OptimizedNotificationQueries:
    """Optimized queries for notification operations."""
    
    @staticmethod
    def get_pending_notifications_batch(batch_size: int = 100):
        """Get pending notifications in optimized batches."""
        from app.models.notification import Notification, NotificationStatus
        from datetime import datetime
        
        return Notification.query.options(
            joinedload(Notification.user),
            joinedload(Notification.template)
        ).filter(
            Notification.status == NotificationStatus.PENDING.value,
            Notification.scheduled_at <= datetime.utcnow()
        ).order_by(Notification.scheduled_at.asc()).limit(batch_size).all()
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=180, key_prefix='notification_stats')
    def get_notification_statistics(tenant_id: Optional[int] = None, days: int = 7):
        """Get notification statistics for the last N days."""
        from app.models.notification import Notification
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        query = db.session.query(
            Notification.status,
            func.count(Notification.id).label('count')
        ).filter(
            Notification.created_at >= cutoff_date
        )
        
        if tenant_id:
            query = query.join(Notification.user).filter(
                Notification.user.has(tenant_id=tenant_id)
            )
        
        stats = query.group_by(Notification.status).all()
        
        return {stat.status: stat.count for stat in stats}


class OptimizedAuditQueries:
    """Optimized queries for audit log operations."""
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=300, key_prefix='audit')
    def get_recent_audit_logs(tenant_id: int, limit: int = 50, action_filter: Optional[str] = None):
        """Get recent audit logs with optimized loading."""
        from app.models.audit_log import AuditLog
        
        query = AuditLog.query.options(
            joinedload(AuditLog.user)
        ).filter(
            AuditLog.tenant_id == tenant_id
        )
        
        if action_filter:
            query = query.filter(AuditLog.action.ilike(f'%{action_filter}%'))
        
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    @staticmethod
    @performance_optimizer.cached_query(timeout=600, key_prefix='audit_stats')
    def get_audit_statistics(tenant_id: int, days: int = 30):
        """Get audit statistics for the last N days."""
        from app.models.audit_log import AuditLog
        from datetime import datetime, timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Action distribution
        action_stats = db.session.query(
            AuditLog.action,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff_date
        ).group_by(AuditLog.action).order_by(func.count(AuditLog.id).desc()).all()
        
        # User activity
        user_stats = db.session.query(
            AuditLog.user_id,
            func.count(AuditLog.id).label('count')
        ).filter(
            AuditLog.tenant_id == tenant_id,
            AuditLog.created_at >= cutoff_date
        ).group_by(AuditLog.user_id).order_by(func.count(AuditLog.id).desc()).limit(10).all()
        
        return {
            'action_distribution': {stat.action: stat.count for stat in action_stats},
            'top_users': [{'user_id': stat.user_id, 'count': stat.count} for stat in user_stats]
        }


def create_database_indexes():
    """Create database indexes for optimal query performance."""
    try:
        # Common indexes for better performance
        indexes = [
            # User indexes
            "CREATE INDEX IF NOT EXISTS idx_users_email_tenant ON users(email, tenant_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_active_tenant ON users(is_active, tenant_id, deleted_at)",
            
            # Lead indexes
            "CREATE INDEX IF NOT EXISTS idx_leads_tenant_updated ON leads(tenant_id, updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_leads_assigned_status ON leads(assigned_to_id, status)",
            
            # Task indexes
            "CREATE INDEX IF NOT EXISTS idx_tasks_tenant_due ON tasks(tenant_id, due_date)",
            "CREATE INDEX IF NOT EXISTS idx_tasks_assigned_status ON tasks(assigned_to_id, status)",
            
            # Notification indexes
            "CREATE INDEX IF NOT EXISTS idx_notifications_status_scheduled ON notifications(status, scheduled_at)",
            "CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at)",
            
            # Audit log indexes
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_tenant_created ON audit_logs(tenant_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action)",
            
            # Usage event indexes
            "CREATE INDEX IF NOT EXISTS idx_usage_events_tenant_created ON usage_events(tenant_id, created_at)",
            "CREATE INDEX IF NOT EXISTS idx_usage_events_subscription ON usage_events(subscription_id, created_at)",
            
            # Knowledge indexes
            "CREATE INDEX IF NOT EXISTS idx_documents_tenant_updated ON documents(tenant_id, updated_at)",
            "CREATE INDEX IF NOT EXISTS idx_chunks_document ON chunks(document_id)",
        ]
        
        for index_sql in indexes:
            try:
                db.session.execute(text(index_sql))
                logger.debug("Created index", sql=index_sql)
            except Exception as e:
                # Index might already exist, which is fine
                logger.debug("Index creation skipped", sql=index_sql, error=str(e))
        
        db.session.commit()
        logger.info("Database indexes created/verified")
        
    except Exception as e:
        logger.error("Failed to create database indexes", error=str(e))
        db.session.rollback()


def analyze_query_performance():
    """Analyze current query performance and suggest optimizations."""
    if not hasattr(current_app, 'performance_optimizer'):
        return {'error': 'Performance optimizer not initialized'}
    
    stats = current_app.performance_optimizer.get_comprehensive_stats()
    
    suggestions = []
    
    # Analyze database queries
    db_stats = stats.get('database', {})
    for query_type, data in db_stats.items():
        if data.get('avg_time_ms', 0) > 500:
            suggestions.append(f"Consider optimizing {query_type} queries (avg: {data['avg_time_ms']:.1f}ms)")
        
        if data.get('slow_queries', 0) > 0:
            suggestions.append(f"{query_type} has {data['slow_queries']} slow queries")
    
    # Analyze cache performance
    cache_stats = stats.get('cache', {})
    hit_rate = cache_stats.get('hit_rate_percent', 0)
    if hit_rate < 70:
        suggestions.append(f"Cache hit rate is low ({hit_rate:.1f}%) - consider caching more queries")
    
    # Analyze request performance
    request_stats = stats.get('requests', {})
    avg_response = request_stats.get('avg_response_time_ms', 0)
    if avg_response > 1000:
        suggestions.append(f"Average response time is high ({avg_response:.1f}ms)")
    
    return {
        'stats': stats,
        'suggestions': suggestions,
        'timestamp': stats.get('timestamp')
    }