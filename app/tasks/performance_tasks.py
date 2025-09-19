"""Celery tasks for performance monitoring."""
import logging
from datetime import datetime, timedelta
from celery import shared_task

from app.utils.performance_alerts import threshold_checker, alert_manager
from app.models.performance import PerformanceMetric, SlowQuery, PerformanceAlert
from app.utils.application_context_manager import get_context_manager


logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def check_performance_thresholds(self):
    """Check performance thresholds and create alerts with proper Flask context."""
    try:
        logger.info("🔍 Checking performance thresholds...")
        
        context_manager = get_context_manager()
        if context_manager:
            context_manager.run_with_context(threshold_checker.run_all_checks)
        else:
            threshold_checker.run_all_checks()
            
        logger.info("✅ Performance threshold check completed")
        return {"status": "success", "message": "Threshold check completed"}
    except Exception as e:
        logger.error(f"Performance threshold check failed: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True, max_retries=3)
def send_performance_alerts(self):
    """Send pending performance alerts with proper Flask context."""
    try:
        logger.info("📧 Sending performance alerts...")
        
        context_manager = get_context_manager()
        if context_manager:
            context_manager.run_with_context(alert_manager.check_and_send_alerts)
        else:
            alert_manager.check_and_send_alerts()
            
        logger.info("✅ Performance alerts sent")
        return {"status": "success", "message": "Alerts sent successfully"}
    except Exception as e:
        logger.error(f"Failed to send performance alerts: {e}")
        raise self.retry(exc=e, countdown=60)


@shared_task(bind=True)
def cleanup_old_performance_data(self, retention_days=30):
    """Clean up old performance monitoring data."""
    try:
        logger.info(f"🧹 Cleaning up performance data older than {retention_days} days...")
        
        # Clean up performance metrics
        deleted_metrics = PerformanceMetric.cleanup_old_metrics(retention_days)
        logger.info(f"Deleted {deleted_metrics} old performance metrics")
        
        # Clean up slow queries
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        deleted_queries = SlowQuery.query.filter(SlowQuery.timestamp < cutoff_date).delete()
        logger.info(f"Deleted {deleted_queries} old slow queries")
        
        # Clean up resolved alerts older than 7 days
        alert_cutoff = datetime.utcnow() - timedelta(days=7)
        deleted_alerts = PerformanceAlert.query.filter(
            PerformanceAlert.status == 'resolved',
            PerformanceAlert.resolved_at < alert_cutoff
        ).delete()
        logger.info(f"Deleted {deleted_alerts} old resolved alerts")
        
        logger.info("✅ Performance data cleanup completed")
        return {
            "status": "success",
            "deleted_metrics": deleted_metrics,
            "deleted_queries": deleted_queries,
            "deleted_alerts": deleted_alerts
        }
    except Exception as e:
        logger.error(f"Performance data cleanup failed: {e}")
        raise


@shared_task(bind=True)
def generate_performance_report(self, hours=24):
    """Generate and optionally send performance report."""
    try:
        logger.info(f"📊 Generating performance report for last {hours} hours...")
        
        from app.utils.performance_monitor import PerformanceCollector
        
        # Collect performance data
        endpoints = PerformanceCollector.get_endpoint_performance_summary(hours)
        slow_queries = PerformanceCollector.get_slow_queries_summary(hours)
        system_health = PerformanceCollector.get_system_health_summary()
        
        # Create report data
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "period_hours": hours,
            "endpoints": endpoints,
            "slow_queries": slow_queries,
            "system_health": system_health,
            "summary": {
                "total_requests": sum(e['request_count'] for e in endpoints),
                "total_errors": sum(e['error_count'] for e in endpoints),
                "avg_response_time": sum(e['avg_response_time'] * e['request_count'] for e in endpoints) / sum(e['request_count'] for e in endpoints) if endpoints else 0,
                "slow_query_count": len(slow_queries),
                "active_alerts": system_health.get('alerts', {}).get('total', 0)
            }
        }
        
        logger.info("✅ Performance report generated")
        return {"status": "success", "report": report}
        
    except Exception as e:
        logger.error(f"Performance report generation failed: {e}")
        raise


@shared_task(bind=True)
def monitor_system_resources(self):
    """Monitor system resources and create alerts if needed."""
    try:
        import psutil
        from flask import current_app
        from app.models.performance import ServiceHealth, PerformanceAlert
        
        logger.info("🖥️ Monitoring system resources...")
        
        # Monitor CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        cpu_threshold = current_app.config.get('CPU_ALERT_THRESHOLD', 85.0)
        
        if cpu_usage >= cpu_threshold:
            PerformanceAlert.create_or_update_alert(
                alert_type='high_cpu_usage',
                severity='high' if cpu_usage >= 95 else 'medium',
                title='High CPU Usage',
                description=f'CPU usage is {cpu_usage:.1f}%',
                service_name='system',
                metric_value=cpu_usage,
                threshold_value=cpu_threshold
            )
        
        # Monitor memory usage
        memory = psutil.virtual_memory()
        memory_threshold = current_app.config.get('MEMORY_ALERT_THRESHOLD', 90.0)
        
        if memory.percent >= memory_threshold:
            PerformanceAlert.create_or_update_alert(
                alert_type='high_memory_usage',
                severity='high' if memory.percent >= 95 else 'medium',
                title='High Memory Usage',
                description=f'Memory usage is {memory.percent:.1f}%',
                service_name='system',
                metric_value=memory.percent,
                threshold_value=memory_threshold
            )
        
        # Monitor disk usage
        disk = psutil.disk_usage('/')
        disk_threshold = current_app.config.get('DISK_ALERT_THRESHOLD', 95.0)
        disk_percent = (disk.used / disk.total) * 100
        
        if disk_percent >= disk_threshold:
            PerformanceAlert.create_or_update_alert(
                alert_type='high_disk_usage',
                severity='critical' if disk_percent >= 98 else 'high',
                title='High Disk Usage',
                description=f'Disk usage is {disk_percent:.1f}%',
                service_name='system',
                metric_value=disk_percent,
                threshold_value=disk_threshold
            )
        
        # Update system health status
        ServiceHealth.update_service_status(
            service_name='system',
            service_type='system',
            status='healthy' if cpu_usage < cpu_threshold and memory.percent < memory_threshold else 'degraded',
            response_time_ms=None,
            extra_metadata={
                'cpu_usage': cpu_usage,
                'memory_usage': memory.percent,
                'disk_usage': disk_percent
            }
        )
        
        logger.info("✅ System resource monitoring completed")
        return {
            "status": "success",
            "cpu_usage": cpu_usage,
            "memory_usage": memory.percent,
            "disk_usage": disk_percent
        }
        
    except Exception as e:
        logger.error(f"System resource monitoring failed: {e}")
        raise


@shared_task(bind=True)
def check_service_health(self):
    """Check health of external services."""
    try:
        import redis
        import requests
        from sqlalchemy import text
        from flask import current_app
        from app.models.performance import ServiceHealth
        from app import db
        
        logger.info("🏥 Checking service health...")
        
        # Check database health
        try:
            db.session.execute(text('SELECT 1'))
            ServiceHealth.update_service_status(
                service_name='database',
                service_type='database',
                status='healthy',
                check_type='query'
            )
        except Exception as e:
            ServiceHealth.update_service_status(
                service_name='database',
                service_type='database',
                status='unavailable',
                check_type='query',
                error_message=str(e)
            )
        
        # Check Redis health
        redis_url = current_app.config.get('REDIS_URL')
        if redis_url:
            try:
                r = redis.from_url(redis_url, socket_connect_timeout=5)
                r.ping()
                ServiceHealth.update_service_status(
                    service_name='redis',
                    service_type='cache',
                    status='healthy',
                    check_type='ping'
                )
            except Exception as e:
                ServiceHealth.update_service_status(
                    service_name='redis',
                    service_type='cache',
                    status='unavailable',
                    check_type='ping',
                    error_message=str(e)
                )
        
        # Check external APIs (example)
        external_services = [
            ('openai', 'https://api.openai.com/v1/models'),
            ('stripe', 'https://api.stripe.com/v1/account'),
        ]
        
        for service_name, url in external_services:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code < 400:
                    ServiceHealth.update_service_status(
                        service_name=service_name,
                        service_type='external_api',
                        status='healthy',
                        check_type='api_call',
                        response_time_ms=response.elapsed.total_seconds() * 1000
                    )
                else:
                    ServiceHealth.update_service_status(
                        service_name=service_name,
                        service_type='external_api',
                        status='degraded',
                        check_type='api_call',
                        error_message=f'HTTP {response.status_code}'
                    )
            except Exception as e:
                ServiceHealth.update_service_status(
                    service_name=service_name,
                    service_type='external_api',
                    status='unavailable',
                    check_type='api_call',
                    error_message=str(e)
                )
        
        logger.info("✅ Service health check completed")
        return {"status": "success", "message": "Service health check completed"}
        
    except Exception as e:
        logger.error(f"Service health check failed: {e}")
        raise


@shared_task(bind=True)
def analyze_performance_trends(self, days=7):
    """Analyze performance trends over time."""
    try:
        from sqlalchemy import func
        from app.models.performance import PerformanceMetric
        
        logger.info(f"📈 Analyzing performance trends over last {days} days...")
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Get daily performance trends
        daily_stats = db.session.query(
            func.date(PerformanceMetric.timestamp).label('date'),
            func.count(PerformanceMetric.id).label('request_count'),
            func.avg(PerformanceMetric.response_time_ms).label('avg_response_time'),
            func.sum(func.case([(PerformanceMetric.status_code >= 400, 1)], else_=0)).label('error_count')
        ).filter(
            PerformanceMetric.timestamp >= since
        ).group_by(
            func.date(PerformanceMetric.timestamp)
        ).order_by(
            func.date(PerformanceMetric.timestamp)
        ).all()
        
        trends = []
        for stat in daily_stats:
            error_rate = (stat.error_count or 0) / max(stat.request_count, 1)
            trends.append({
                'date': stat.date.isoformat(),
                'request_count': stat.request_count,
                'avg_response_time': float(stat.avg_response_time or 0),
                'error_count': stat.error_count or 0,
                'error_rate': error_rate
            })
        
        # Detect significant changes
        alerts_created = 0
        if len(trends) >= 2:
            latest = trends[-1]
            previous = trends[-2]
            
            # Check for significant response time increase
            if latest['avg_response_time'] > previous['avg_response_time'] * 1.5:
                PerformanceAlert.create_or_update_alert(
                    alert_type='performance_degradation',
                    severity='medium',
                    title='Performance Degradation Detected',
                    description=f'Average response time increased from {previous["avg_response_time"]:.0f}ms to {latest["avg_response_time"]:.0f}ms',
                    metric_value=latest['avg_response_time'],
                    threshold_value=previous['avg_response_time'] * 1.5
                )
                alerts_created += 1
            
            # Check for significant error rate increase
            if latest['error_rate'] > previous['error_rate'] * 2 and latest['error_rate'] > 0.01:
                PerformanceAlert.create_or_update_alert(
                    alert_type='error_rate_increase',
                    severity='high',
                    title='Error Rate Increase Detected',
                    description=f'Error rate increased from {previous["error_rate"]:.1%} to {latest["error_rate"]:.1%}',
                    metric_value=latest['error_rate'],
                    threshold_value=previous['error_rate'] * 2
                )
                alerts_created += 1
        
        logger.info(f"✅ Performance trend analysis completed, {alerts_created} alerts created")
        return {
            "status": "success",
            "trends": trends,
            "alerts_created": alerts_created
        }
        
    except Exception as e:
        logger.error(f"Performance trend analysis failed: {e}")
        raise