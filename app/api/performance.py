"""Performance monitoring API endpoints."""
from flask import Blueprint, jsonify, request, current_app
from datetime import datetime, timedelta

from app.models.performance import PerformanceMetric, SlowQuery, ServiceHealth, PerformanceAlert
from app.utils.performance_monitor import PerformanceCollector
from app.utils.response import api_response, error_response


performance_bp = Blueprint('performance', __name__)


@performance_bp.route('/metrics/summary', methods=['GET'])
def get_performance_summary():
    """Get performance metrics summary."""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        # Get endpoint performance summary
        endpoints = PerformanceCollector.get_endpoint_performance_summary(hours)
        
        # Get slow queries summary
        slow_queries = PerformanceCollector.get_slow_queries_summary(hours)
        
        # Get system health summary
        system_health = PerformanceCollector.get_system_health_summary()
        
        return api_response({
            'endpoints': endpoints,
            'slow_queries': slow_queries,
            'system_health': system_health,
            'period_hours': hours
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get performance summary: {e}")
        return error_response('Failed to retrieve performance summary', 500)


@performance_bp.route('/metrics/endpoints', methods=['GET'])
def get_endpoint_metrics():
    """Get detailed metrics for endpoints."""
    try:
        hours = request.args.get('hours', 24, type=int)
        endpoint = request.args.get('endpoint')
        
        if endpoint:
            # Get metrics for specific endpoint
            stats = PerformanceMetric.get_endpoint_stats(endpoint, hours)
            return api_response({
                'endpoint': endpoint,
                'stats': stats,
                'period_hours': hours
            })
        else:
            # Get metrics for all endpoints
            endpoints = PerformanceCollector.get_endpoint_performance_summary(hours)
            return api_response({
                'endpoints': endpoints,
                'period_hours': hours
            })
            
    except Exception as e:
        current_app.logger.error(f"Failed to get endpoint metrics: {e}")
        return error_response('Failed to retrieve endpoint metrics', 500)


@performance_bp.route('/metrics/slow-requests', methods=['GET'])
def get_slow_requests():
    """Get slow requests."""
    try:
        threshold = request.args.get('threshold', 2000, type=int)
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 50, type=int)
        
        slow_requests = PerformanceMetric.get_slow_requests(threshold, hours)
        
        # Limit results
        if limit:
            slow_requests = slow_requests[:limit]
        
        # Convert to dict format
        results = []
        for request_metric in slow_requests:
            results.append({
                'id': request_metric.id,
                'endpoint': request_metric.endpoint,
                'method': request_metric.method,
                'response_time_ms': request_metric.response_time_ms,
                'status_code': request_metric.status_code,
                'timestamp': request_metric.timestamp.isoformat(),
                'user_id': request_metric.user_id,
                'ip_address': request_metric.ip_address
            })
        
        return api_response({
            'slow_requests': results,
            'threshold_ms': threshold,
            'period_hours': hours,
            'total_count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get slow requests: {e}")
        return error_response('Failed to retrieve slow requests', 500)


@performance_bp.route('/metrics/slow-queries', methods=['GET'])
def get_slow_queries():
    """Get slow database queries."""
    try:
        hours = request.args.get('hours', 24, type=int)
        limit = request.args.get('limit', 20, type=int)
        
        slow_queries = SlowQuery.get_frequent_slow_queries(hours, limit)
        
        # Convert to dict format
        results = []
        for query in slow_queries:
            results.append({
                'query_hash': query.query_hash,
                'normalized_query': query.normalized_query,
                'occurrence_count': query.occurrence_count,
                'avg_execution_time': float(query.avg_execution_time),
                'max_execution_time': float(query.max_execution_time)
            })
        
        return api_response({
            'slow_queries': results,
            'period_hours': hours,
            'total_count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get slow queries: {e}")
        return error_response('Failed to retrieve slow queries', 500)


@performance_bp.route('/alerts', methods=['GET'])
def get_performance_alerts():
    """Get performance alerts."""
    try:
        status = request.args.get('status', 'active')
        severity = request.args.get('severity')
        hours = request.args.get('hours', 24, type=int)
        
        query = PerformanceAlert.query
        
        if status:
            query = query.filter_by(status=status)
        
        if severity:
            query = query.filter_by(severity=severity)
        
        if hours:
            since = datetime.utcnow() - timedelta(hours=hours)
            query = query.filter(PerformanceAlert.first_occurrence >= since)
        
        alerts = query.order_by(PerformanceAlert.first_occurrence.desc()).all()
        
        # Convert to dict format
        results = []
        for alert in alerts:
            results.append({
                'id': alert.id,
                'alert_type': alert.alert_type,
                'severity': alert.severity,
                'title': alert.title,
                'description': alert.description,
                'endpoint': alert.endpoint,
                'service_name': alert.service_name,
                'metric_value': alert.metric_value,
                'threshold_value': alert.threshold_value,
                'status': alert.status,
                'first_occurrence': alert.first_occurrence.isoformat(),
                'last_occurrence': alert.last_occurrence.isoformat(),
                'occurrence_count': alert.occurrence_count,
                'acknowledged_by': alert.acknowledged_by,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                'alert_metadata': alert.alert_metadata
            })
        
        return api_response({
            'alerts': results,
            'total_count': len(results),
            'filters': {
                'status': status,
                'severity': severity,
                'hours': hours
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get performance alerts: {e}")
        return error_response('Failed to retrieve performance alerts', 500)


@performance_bp.route('/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge a performance alert."""
    try:
        # For now, use a default user ID (this should be replaced with proper auth)
        user_id = 1
        
        alert = PerformanceAlert.acknowledge_alert(alert_id, user_id)
        
        if not alert:
            return error_response('Alert not found or cannot be acknowledged', 404)
        
        return api_response({
            'message': 'Alert acknowledged successfully',
            'alert_id': alert_id,
            'acknowledged_by': user_id,
            'acknowledged_at': alert.acknowledged_at.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to acknowledge alert: {e}")
        return error_response('Failed to acknowledge alert', 500)


@performance_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """Resolve a performance alert."""
    try:
        alert = PerformanceAlert.resolve_alert(alert_id)
        
        if not alert:
            return error_response('Alert not found or cannot be resolved', 404)
        
        return api_response({
            'message': 'Alert resolved successfully',
            'alert_id': alert_id,
            'resolved_at': alert.resolved_at.isoformat()
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to resolve alert: {e}")
        return error_response('Failed to resolve alert', 500)


@performance_bp.route('/services/health', methods=['GET'])
def get_service_health():
    """Get service health status."""
    try:
        services = ServiceHealth.query.order_by(ServiceHealth.service_name).all()
        
        # Convert to dict format
        results = []
        for service in services:
            results.append({
                'id': service.id,
                'service_name': service.service_name,
                'service_type': service.service_type,
                'status': service.status,
                'response_time_ms': service.response_time_ms,
                'error_message': service.error_message,
                'check_type': service.check_type,
                'last_check': service.last_check.isoformat(),
                'version': service.version,
                'extra_metadata': service.extra_metadata
            })
        
        # Get summary
        summary = ServiceHealth.get_service_status_summary()
        status_counts = {status: count for status, count in summary}
        
        return api_response({
            'services': results,
            'summary': status_counts,
            'total_count': len(results)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get service health: {e}")
        return error_response('Failed to retrieve service health', 500)


@performance_bp.route('/system/health', methods=['GET'])
def get_system_health():
    """Get overall system health."""
    try:
        health = PerformanceCollector.get_system_health_summary()
        return api_response(health)
        
    except Exception as e:
        current_app.logger.error(f"Failed to get system health: {e}")
        return error_response('Failed to retrieve system health', 500)


@performance_bp.route('/dashboard', methods=['GET'])
def get_performance_dashboard():
    """Get performance dashboard data."""
    try:
        hours = request.args.get('hours', 24, type=int)
        
        # Get all dashboard data
        endpoints = PerformanceCollector.get_endpoint_performance_summary(hours)
        slow_queries = PerformanceCollector.get_slow_queries_summary(hours)
        system_health = PerformanceCollector.get_system_health_summary()
        
        # Get recent alerts
        recent_alerts = PerformanceAlert.query.filter_by(status='active').order_by(
            PerformanceAlert.first_occurrence.desc()
        ).limit(10).all()
        
        alerts_data = []
        for alert in recent_alerts:
            alerts_data.append({
                'id': alert.id,
                'severity': alert.severity,
                'title': alert.title,
                'first_occurrence': alert.first_occurrence.isoformat(),
                'occurrence_count': alert.occurrence_count
            })
        
        # Calculate summary statistics
        total_requests = sum(e['request_count'] for e in endpoints)
        total_errors = sum(e['error_count'] for e in endpoints)
        avg_response_time = sum(e['avg_response_time'] * e['request_count'] for e in endpoints) / total_requests if total_requests > 0 else 0
        
        return api_response({
            'summary': {
                'total_requests': total_requests,
                'total_errors': total_errors,
                'error_rate': total_errors / total_requests if total_requests > 0 else 0,
                'avg_response_time': avg_response_time,
                'active_alerts': len(alerts_data),
                'slow_queries': len(slow_queries)
            },
            'endpoints': endpoints[:10],  # Top 10 endpoints
            'slow_queries': slow_queries[:5],  # Top 5 slow queries
            'system_health': system_health,
            'recent_alerts': alerts_data,
            'period_hours': hours
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get performance dashboard: {e}")
        return error_response('Failed to retrieve performance dashboard', 500)


@performance_bp.route('/config', methods=['GET'])
def get_performance_config():
    """Get performance monitoring configuration."""
    try:
        config = {
            'monitoring_enabled': current_app.config.get('MONITORING_ENABLED', True),
            'alerting_enabled': current_app.config.get('ALERTING_ENABLED', True),
            'performance_log_threshold_ms': current_app.config.get('PERFORMANCE_LOG_THRESHOLD_MS', 1000),
            'slow_query_threshold_ms': current_app.config.get('SLOW_QUERY_THRESHOLD_MS', 1000),
            'slow_request_threshold_ms': current_app.config.get('SLOW_REQUEST_THRESHOLD_MS', 2000),
            'metrics_retention_days': current_app.config.get('METRICS_RETENTION_DAYS', 30),
            'cpu_alert_threshold': current_app.config.get('CPU_ALERT_THRESHOLD', 85.0),
            'memory_alert_threshold': current_app.config.get('MEMORY_ALERT_THRESHOLD', 90.0),
            'disk_alert_threshold': current_app.config.get('DISK_ALERT_THRESHOLD', 95.0),
            'error_rate_threshold': current_app.config.get('ERROR_RATE_THRESHOLD', 0.05),
            'response_time_threshold': current_app.config.get('RESPONSE_TIME_THRESHOLD', 2000)
        }
        
        return api_response({'config': config})
        
    except Exception as e:
        current_app.logger.error(f"Failed to get performance config: {e}")
        return error_response('Failed to retrieve performance configuration', 500)