"""Performance monitoring CLI commands."""
import click
from datetime import datetime, timedelta
from flask import current_app
from flask.cli import with_appcontext

from app.models.performance import PerformanceMetric, SlowQuery, ServiceHealth, PerformanceAlert
from app.utils.performance_monitor import PerformanceCollector
from app.utils.performance_alerts import threshold_checker, alert_manager


@click.group()
def performance():
    """Performance monitoring commands."""
    pass


@performance.command()
@click.option('--hours', default=24, help='Hours to look back for metrics')
@with_appcontext
def report(hours):
    """Generate performance report."""
    click.echo(f"📊 Performance Report (Last {hours} hours)")
    click.echo("=" * 50)
    
    # Endpoint performance summary
    click.echo("\n🌐 Endpoint Performance:")
    endpoints = PerformanceCollector.get_endpoint_performance_summary(hours)
    
    if endpoints:
        click.echo(f"{'Endpoint':<30} {'Requests':<10} {'Avg Time':<10} {'Errors':<8} {'Error Rate':<10}")
        click.echo("-" * 78)
        for endpoint in endpoints[:10]:  # Top 10
            click.echo(
                f"{endpoint['endpoint'][:29]:<30} "
                f"{endpoint['request_count']:<10} "
                f"{endpoint['avg_response_time']:<10.0f} "
                f"{endpoint['error_count']:<8} "
                f"{endpoint['error_rate']:<10.1%}"
            )
    else:
        click.echo("No endpoint data available")
    
    # Slow queries summary
    click.echo("\n🐌 Slow Queries:")
    slow_queries = PerformanceCollector.get_slow_queries_summary(hours)
    
    if slow_queries:
        click.echo(f"{'Count':<8} {'Avg Time':<10} {'Max Time':<10} {'Query':<50}")
        click.echo("-" * 78)
        for query in slow_queries[:5]:  # Top 5
            click.echo(
                f"{query['occurrence_count']:<8} "
                f"{query['avg_execution_time']:<10.0f} "
                f"{query['max_execution_time']:<10.0f} "
                f"{query['normalized_query'][:49]:<50}"
            )
    else:
        click.echo("No slow queries detected")
    
    # System health summary
    click.echo("\n🏥 System Health:")
    health = PerformanceCollector.get_system_health_summary()
    
    if 'error' not in health:
        click.echo(f"CPU Usage: {health['system']['cpu_usage']:.1f}%")
        click.echo(f"Memory Usage: {health['system']['memory_usage']:.1f}%")
        click.echo(f"Disk Usage: {health['system']['disk_usage']:.1f}%")
        
        if health['alerts']['total'] > 0:
            click.echo(f"\n⚠️  Active Alerts: {health['alerts']['total']}")
            for severity, count in health['alerts']['by_severity'].items():
                click.echo(f"  {severity.title()}: {count}")
        else:
            click.echo("\n✅ No active alerts")
    else:
        click.echo(f"Error getting system health: {health['error']}")


@performance.command()
@click.option('--threshold', default=2000, help='Response time threshold in milliseconds')
@click.option('--hours', default=1, help='Hours to look back')
@with_appcontext
def slow_requests(threshold, hours):
    """Show slow requests."""
    click.echo(f"🐌 Slow Requests (>{threshold}ms in last {hours} hours)")
    click.echo("=" * 60)
    
    slow = PerformanceMetric.get_slow_requests(threshold, hours)
    
    if slow:
        click.echo(f"{'Time':<20} {'Endpoint':<30} {'Method':<8} {'Time (ms)':<10}")
        click.echo("-" * 68)
        for request in slow[:20]:  # Top 20
            click.echo(
                f"{request.timestamp.strftime('%Y-%m-%d %H:%M:%S'):<20} "
                f"{request.endpoint[:29]:<30} "
                f"{request.method:<8} "
                f"{request.response_time_ms:<10.0f}"
            )
    else:
        click.echo("No slow requests found")


@performance.command()
@click.option('--hours', default=24, help='Hours to look back')
@with_appcontext
def alerts(hours):
    """Show performance alerts."""
    click.echo(f"🚨 Performance Alerts (Last {hours} hours)")
    click.echo("=" * 50)
    
    since = datetime.utcnow() - timedelta(hours=hours)
    alerts = PerformanceAlert.query.filter(
        PerformanceAlert.first_occurrence >= since
    ).order_by(PerformanceAlert.first_occurrence.desc()).all()
    
    if alerts:
        click.echo(f"{'Time':<20} {'Severity':<10} {'Type':<20} {'Title':<30}")
        click.echo("-" * 80)
        for alert in alerts:
            click.echo(
                f"{alert.first_occurrence.strftime('%Y-%m-%d %H:%M:%S'):<20} "
                f"{alert.severity.upper():<10} "
                f"{alert.alert_type:<20} "
                f"{alert.title[:29]:<30}"
            )
    else:
        click.echo("No alerts found")


@performance.command()
@click.option('--days', default=30, help='Retention period in days')
@with_appcontext
def cleanup(days):
    """Clean up old performance data."""
    click.echo(f"🧹 Cleaning up performance data older than {days} days...")
    
    # Clean up performance metrics
    deleted_metrics = PerformanceMetric.cleanup_old_metrics(days)
    click.echo(f"Deleted {deleted_metrics} old performance metrics")
    
    # Clean up slow queries
    cutoff_date = datetime.utcnow() - timedelta(days=days)
    deleted_queries = SlowQuery.query.filter(SlowQuery.timestamp < cutoff_date).delete()
    click.echo(f"Deleted {deleted_queries} old slow queries")
    
    # Clean up resolved alerts older than 7 days
    alert_cutoff = datetime.utcnow() - timedelta(days=7)
    deleted_alerts = PerformanceAlert.query.filter(
        PerformanceAlert.status == 'resolved',
        PerformanceAlert.resolved_at < alert_cutoff
    ).delete()
    click.echo(f"Deleted {deleted_alerts} old resolved alerts")
    
    click.echo("✅ Cleanup completed")


@performance.command()
@with_appcontext
def check_thresholds():
    """Check performance thresholds and create alerts."""
    click.echo("🔍 Checking performance thresholds...")
    
    threshold_checker.run_all_checks()
    
    click.echo("✅ Threshold check completed")


@performance.command()
@with_appcontext
def send_alerts():
    """Send pending performance alerts."""
    click.echo("📧 Sending performance alerts...")
    
    alert_manager.check_and_send_alerts()
    
    click.echo("✅ Alert sending completed")


@performance.command()
@click.argument('alert_id', type=int)
@with_appcontext
def acknowledge(alert_id):
    """Acknowledge a performance alert."""
    alert = PerformanceAlert.query.get(alert_id)
    
    if not alert:
        click.echo(f"❌ Alert {alert_id} not found")
        return
    
    if alert.status != 'active':
        click.echo(f"❌ Alert {alert_id} is not active (status: {alert.status})")
        return
    
    # For CLI, we'll use a system user ID of 0
    PerformanceAlert.acknowledge_alert(alert_id, 0)
    click.echo(f"✅ Alert {alert_id} acknowledged")


@performance.command()
@click.argument('alert_id', type=int)
@with_appcontext
def resolve(alert_id):
    """Resolve a performance alert."""
    alert = PerformanceAlert.query.get(alert_id)
    
    if not alert:
        click.echo(f"❌ Alert {alert_id} not found")
        return
    
    if alert.status == 'resolved':
        click.echo(f"❌ Alert {alert_id} is already resolved")
        return
    
    PerformanceAlert.resolve_alert(alert_id)
    click.echo(f"✅ Alert {alert_id} resolved")


@performance.command()
@with_appcontext
def services():
    """Show service health status."""
    click.echo("🏥 Service Health Status")
    click.echo("=" * 40)
    
    services = ServiceHealth.query.order_by(ServiceHealth.service_name).all()
    
    if services:
        click.echo(f"{'Service':<20} {'Type':<15} {'Status':<12} {'Last Check':<20}")
        click.echo("-" * 67)
        for service in services:
            status_icon = "✅" if service.status == 'healthy' else "⚠️" if service.status == 'degraded' else "❌"
            click.echo(
                f"{service.service_name:<20} "
                f"{service.service_type:<15} "
                f"{status_icon} {service.status:<10} "
                f"{service.last_check.strftime('%Y-%m-%d %H:%M:%S'):<20}"
            )
    else:
        click.echo("No service health data available")


@performance.command()
@click.option('--endpoint', help='Specific endpoint to analyze')
@click.option('--hours', default=24, help='Hours to analyze')
@with_appcontext
def analyze(endpoint, hours):
    """Analyze performance for specific endpoint or all endpoints."""
    if endpoint:
        click.echo(f"📈 Performance Analysis for {endpoint} (Last {hours} hours)")
        click.echo("=" * 60)
        
        stats = PerformanceMetric.get_endpoint_stats(endpoint, hours)
        
        if stats['request_count'] > 0:
            click.echo(f"Total Requests: {stats['request_count']}")
            click.echo(f"Average Response Time: {stats['avg_response_time']:.0f}ms")
            click.echo(f"Min Response Time: {stats['min_response_time']:.0f}ms")
            click.echo(f"Max Response Time: {stats['max_response_time']:.0f}ms")
            click.echo(f"95th Percentile: {stats['p95_response_time']:.0f}ms")
            click.echo(f"Error Count: {stats['error_count']}")
            click.echo(f"Error Rate: {stats['error_rate']:.1%}")
        else:
            click.echo("No data available for this endpoint")
    else:
        click.echo(f"📈 Overall Performance Analysis (Last {hours} hours)")
        click.echo("=" * 50)
        
        endpoints = PerformanceCollector.get_endpoint_performance_summary(hours)
        
        if endpoints:
            total_requests = sum(e['request_count'] for e in endpoints)
            total_errors = sum(e['error_count'] for e in endpoints)
            avg_response_time = sum(e['avg_response_time'] * e['request_count'] for e in endpoints) / total_requests if total_requests > 0 else 0
            
            click.echo(f"Total Requests: {total_requests}")
            click.echo(f"Total Errors: {total_errors}")
            click.echo(f"Overall Error Rate: {total_errors / total_requests:.1%}" if total_requests > 0 else "Overall Error Rate: 0.0%")
            click.echo(f"Average Response Time: {avg_response_time:.0f}ms")
            
            # Show top 5 slowest endpoints
            slowest = sorted(endpoints, key=lambda x: x['avg_response_time'], reverse=True)[:5]
            click.echo("\n🐌 Slowest Endpoints:")
            for endpoint in slowest:
                click.echo(f"  {endpoint['endpoint']}: {endpoint['avg_response_time']:.0f}ms")
            
            # Show endpoints with highest error rates
            highest_errors = sorted([e for e in endpoints if e['error_rate'] > 0], key=lambda x: x['error_rate'], reverse=True)[:5]
            if highest_errors:
                click.echo("\n❌ Highest Error Rates:")
                for endpoint in highest_errors:
                    click.echo(f"  {endpoint['endpoint']}: {endpoint['error_rate']:.1%}")
        else:
            click.echo("No performance data available")


def init_app(app):
    """Initialize performance CLI commands."""
    app.cli.add_command(performance)