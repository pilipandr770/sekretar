"""Workers package for background task processing."""

from app.workers.base import (
    BaseWorker,
    MonitoredWorker,
    create_task_decorator,
    get_task_status,
    revoke_task,
    get_active_tasks,
    get_worker_stats
)

from app.workers.dead_letter import (
    process_dead_letter_task,
    retry_dead_letter_task,
    cleanup_old_dead_letter_tasks,
    get_dead_letter_stats,
    get_dead_letter_tasks
)

from app.workers.monitoring import (
    TaskQueueMonitor,
    get_queue_health,
    setup_periodic_monitoring
)

from app.workers.billing import (
    sync_stripe_usage,
    enforce_subscription_quotas,
    process_trial_expirations,
    handle_plan_upgrades,
    sync_subscription_status,
    process_failed_payments,
    daily_billing_sync,
    hourly_quota_enforcement
)

from app.workers.kyb_monitoring import (
    collect_counterparty_data,
    detect_counterparty_changes,
    generate_kyb_alerts,
    create_evidence_snapshot,
    schedule_counterparty_monitoring,
    daily_kyb_monitoring,
    cleanup_old_kyb_data
)

from app.workers.notifications import (
    send_notification,
    send_bulk_notifications,
    process_notification_preferences,
    cleanup_old_notifications,
    send_kyb_alert,
    send_invoice_notification,
    send_system_notification,
    daily_notification_cleanup,
    process_scheduled_notifications
)

from app.workers.data_retention import (
    cleanup_expired_data,
    check_expired_consents,
    process_data_deletion_request,
    process_data_export_request,
    cleanup_expired_exports,
    generate_retention_report
)

__all__ = [
    # Base classes
    'BaseWorker',
    'MonitoredWorker',
    'create_task_decorator',
    
    # Task management
    'get_task_status',
    'revoke_task',
    'get_active_tasks',
    'get_worker_stats',
    
    # Dead letter queue
    'process_dead_letter_task',
    'retry_dead_letter_task',
    'cleanup_old_dead_letter_tasks',
    'get_dead_letter_stats',
    'get_dead_letter_tasks',
    
    # Monitoring
    'TaskQueueMonitor',
    'get_queue_health',
    'setup_periodic_monitoring',
    
    # Billing workers
    'sync_stripe_usage',
    'enforce_subscription_quotas',
    'process_trial_expirations',
    'handle_plan_upgrades',
    'sync_subscription_status',
    'process_failed_payments',
    'daily_billing_sync',
    'hourly_quota_enforcement',
    
    # KYB monitoring workers
    'collect_counterparty_data',
    'detect_counterparty_changes',
    'generate_kyb_alerts',
    'create_evidence_snapshot',
    'schedule_counterparty_monitoring',
    'daily_kyb_monitoring',
    'cleanup_old_kyb_data',
    
    # Notification workers
    'send_notification',
    'send_bulk_notifications',
    'process_notification_preferences',
    'cleanup_old_notifications',
    'send_kyb_alert',
    'send_invoice_notification',
    'send_system_notification',
    'daily_notification_cleanup',
    'process_scheduled_notifications',
    
    # Data retention workers
    'cleanup_expired_data',
    'check_expired_consents',
    'process_data_deletion_request',
    'process_data_export_request',
    'cleanup_expired_exports',
    'generate_retention_report'
]