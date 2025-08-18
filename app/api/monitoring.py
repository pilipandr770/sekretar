"""
Monitoring and health check API endpoints.
"""

from flask import Blueprint, jsonify, Response, request
from app.utils.monitoring import (
    health_checker, 
    performance_monitor, 
    get_metrics, 
    get_metrics_content_type
)
from app.services.monitoring_service import monitoring_service
from app.services.alerting_service import alerting_service
from app.services.error_tracking_service import error_tracking_service
from app.services.dashboard_service import dashboard_service
import structlog

logger = structlog.get_logger(__name__)

monitoring_bp = Blueprint('monitoring', __name__)


@monitoring_bp.route('/health', methods=['GET'])
def health_check():
    """
    Comprehensive health check endpoint.
    Returns the status of all registered health checks.
    """
    try:
        health_status = health_checker.run_checks()
        
        # Determine HTTP status code based on health
        status_code = 200 if health_status['status'] == 'healthy' else 503
        
        return jsonify(health_status), status_code
        
    except Exception as e:
        logger.error("Health check endpoint failed", error=str(e))
        return jsonify({
            'status': 'error',
            'message': 'Health check system failure',
            'error': str(e)
        }), 500


@monitoring_bp.route('/health/ready', methods=['GET'])
def readiness_check():
    """
    Kubernetes-style readiness check.
    Returns 200 if the application is ready to serve traffic.
    """
    try:
        # Run only critical health checks for readiness
        health_status = health_checker.run_checks()
        
        # Check if any critical checks failed
        critical_failures = [
            name for name, check in health_status['checks'].items()
            if check.get('critical', True) and check['status'] != 'healthy'
        ]
        
        if critical_failures:
            return jsonify({
                'status': 'not_ready',
                'failed_checks': critical_failures
            }), 503
        
        return jsonify({'status': 'ready'}), 200
        
    except Exception as e:
        logger.error("Readiness check failed", error=str(e))
        return jsonify({
            'status': 'not_ready',
            'error': str(e)
        }), 503


@monitoring_bp.route('/health/live', methods=['GET'])
def liveness_check():
    """
    Kubernetes-style liveness check.
    Returns 200 if the application is alive (basic functionality works).
    """
    try:
        # Simple liveness check - just verify the application is responding
        return jsonify({
            'status': 'alive',
            'timestamp': health_checker.last_check_time.isoformat() if health_checker.last_check_time else None
        }), 200
        
    except Exception as e:
        logger.error("Liveness check failed", error=str(e))
        return jsonify({
            'status': 'dead',
            'error': str(e)
        }), 500


@monitoring_bp.route('/metrics', methods=['GET'])
def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    Returns metrics in Prometheus format.
    """
    try:
        metrics_data = get_metrics()
        return Response(
            metrics_data,
            mimetype=get_metrics_content_type()
        )
    except Exception as e:
        logger.error("Failed to generate metrics", error=str(e))
        return Response(
            "# Failed to generate metrics\n",
            mimetype=get_metrics_content_type(),
            status=500
        )


@monitoring_bp.route('/performance', methods=['GET'])
def performance_status():
    """
    Get current performance metrics and alerts.
    """
    try:
        performance_summary = performance_monitor.get_performance_summary()
        alerts = performance_monitor.check_performance_thresholds()
        
        return jsonify({
            'performance': performance_summary,
            'alerts': alerts,
            'thresholds': performance_monitor.thresholds
        }), 200
        
    except Exception as e:
        logger.error("Failed to get performance status", error=str(e))
        return jsonify({
            'error': 'Failed to get performance status',
            'message': str(e)
        }), 500


@monitoring_bp.route('/status', methods=['GET'])
def system_status():
    """
    Get comprehensive system status including health, performance, and alerts.
    """
    try:
        health_status = health_checker.run_checks()
        performance_summary = performance_monitor.get_performance_summary()
        alerts = performance_monitor.check_performance_thresholds()
        
        # Get active alerts from alerting service
        active_alerts = []
        if alerting_service:
            active_alerts = [alert.to_dict() for alert in alerting_service.get_active_alerts()]
        
        # Determine overall system status
        overall_status = 'healthy'
        if health_status['status'] != 'healthy':
            overall_status = 'unhealthy'
        elif any(alert['severity'] == 'critical' for alert in alerts):
            overall_status = 'degraded'
        elif alerts or active_alerts:
            overall_status = 'warning'
        
        return jsonify({
            'overall_status': overall_status,
            'health': health_status,
            'performance': performance_summary,
            'alerts': alerts,
            'active_alerts': active_alerts,
            'timestamp': health_status.get('timestamp')
        }), 200
        
    except Exception as e:
        logger.error("Failed to get system status", error=str(e))
        return jsonify({
            'overall_status': 'error',
            'error': str(e)
        }), 500


@monitoring_bp.route('/alerts', methods=['GET'])
def get_alerts():
    """Get all active alerts."""
    try:
        if not alerting_service:
            return jsonify({'error': 'Alerting service not available'}), 503
        
        active_alerts = alerting_service.get_active_alerts()
        alert_history = alerting_service.get_alert_history(limit=50)
        
        return jsonify({
            'active_alerts': [alert.to_dict() for alert in active_alerts],
            'alert_history': [alert.to_dict() for alert in alert_history],
            'total_active': len(active_alerts)
        }), 200
        
    except Exception as e:
        logger.error("Failed to get alerts", error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/alerts/<alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Acknowledge an alert."""
    try:
        if not alerting_service:
            return jsonify({'error': 'Alerting service not available'}), 503
        
        data = request.get_json() or {}
        acknowledged_by = data.get('acknowledged_by', 'unknown')
        
        alerting_service.acknowledge_alert(alert_id, acknowledged_by)
        
        return jsonify({
            'message': 'Alert acknowledged',
            'alert_id': alert_id,
            'acknowledged_by': acknowledged_by
        }), 200
        
    except Exception as e:
        logger.error("Failed to acknowledge alert", alert_id=alert_id, error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/alerts/<alert_id>/resolve', methods=['POST'])
def resolve_alert(alert_id):
    """Resolve an alert."""
    try:
        if not alerting_service:
            return jsonify({'error': 'Alerting service not available'}), 503
        
        data = request.get_json() or {}
        resolved_by = data.get('resolved_by', 'unknown')
        
        alerting_service.resolve_alert(alert_id, resolved_by)
        
        return jsonify({
            'message': 'Alert resolved',
            'alert_id': alert_id,
            'resolved_by': resolved_by
        }), 200
        
    except Exception as e:
        logger.error("Failed to resolve alert", alert_id=alert_id, error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/errors', methods=['GET'])
def get_errors():
    """Get error tracking summary."""
    try:
        hours = request.args.get('hours', 24, type=int)
        summary = error_tracking_service.get_error_summary(hours)
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error("Failed to get error summary", error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/errors/<fingerprint>', methods=['GET'])
def get_error_details(fingerprint):
    """Get detailed information about a specific error."""
    try:
        limit = request.args.get('limit', 50, type=int)
        details = error_tracking_service.get_error_details(fingerprint, limit)
        
        if not details:
            return jsonify({'error': 'Error not found'}), 404
        
        return jsonify(details), 200
        
    except Exception as e:
        logger.error("Failed to get error details", fingerprint=fingerprint, error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/errors/trends', methods=['GET'])
def get_error_trends():
    """Get error trends over time."""
    try:
        hours = request.args.get('hours', 24, type=int)
        trends = error_tracking_service.get_error_trends(hours)
        
        return jsonify(trends), 200
        
    except Exception as e:
        logger.error("Failed to get error trends", error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/dashboards', methods=['GET'])
def list_dashboards():
    """List available monitoring dashboards."""
    try:
        dashboards = dashboard_service.list_dashboards()
        return jsonify({'dashboards': dashboards}), 200
        
    except Exception as e:
        logger.error("Failed to list dashboards", error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/dashboards/<dashboard_id>', methods=['GET'])
def get_dashboard(dashboard_id):
    """Get dashboard configuration and data."""
    try:
        dashboard = dashboard_service.get_dashboard(dashboard_id)
        if not dashboard:
            return jsonify({'error': 'Dashboard not found'}), 404
        
        # Get data for all widgets
        dashboard_data = dashboard.to_dict()
        widget_data = {}
        
        for widget in dashboard.widgets:
            try:
                data = dashboard_service.get_widget_data(widget.data_source, widget.config)
                widget_data[widget.id] = data
            except Exception as e:
                logger.warning("Failed to get widget data", widget_id=widget.id, error=str(e))
                widget_data[widget.id] = {'error': str(e)}
        
        dashboard_data['widget_data'] = widget_data
        
        return jsonify(dashboard_data), 200
        
    except Exception as e:
        logger.error("Failed to get dashboard", dashboard_id=dashboard_id, error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/dashboards/<dashboard_id>/widgets/<widget_id>/data', methods=['GET'])
def get_widget_data(dashboard_id, widget_id):
    """Get data for a specific widget."""
    try:
        dashboard = dashboard_service.get_dashboard(dashboard_id)
        if not dashboard:
            return jsonify({'error': 'Dashboard not found'}), 404
        
        # Find the widget
        widget = None
        for w in dashboard.widgets:
            if w.id == widget_id:
                widget = w
                break
        
        if not widget:
            return jsonify({'error': 'Widget not found'}), 404
        
        data = dashboard_service.get_widget_data(widget.data_source, widget.config)
        
        return jsonify({
            'widget_id': widget_id,
            'data': data,
            'timestamp': data.get('timestamp') if isinstance(data, dict) else None
        }), 200
        
    except Exception as e:
        logger.error("Failed to get widget data", 
                    dashboard_id=dashboard_id, widget_id=widget_id, error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/system/resources', methods=['GET'])
def get_system_resources():
    """Get detailed system resource information."""
    try:
        if monitoring_service and monitoring_service.metrics_collector:
            system_metrics = monitoring_service.metrics_collector.get_system_metrics()
            app_metrics = monitoring_service.metrics_collector.get_application_metrics()
            
            return jsonify({
                'system': system_metrics.__dict__,
                'application': app_metrics.__dict__,
                'timestamp': system_metrics.timestamp
            }), 200
        else:
            return jsonify({'error': 'Monitoring service not available'}), 503
            
    except Exception as e:
        logger.error("Failed to get system resources", error=str(e))
        return jsonify({'error': str(e)}), 500


@monitoring_bp.route('/webhooks/alerts', methods=['POST'])
def webhook_alert():
    """Webhook endpoint for external alert systems."""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        logger.info("Alert webhook received", data=data)
        
        # Process the webhook data
        # This could trigger internal alerts or notifications
        
        return jsonify({'message': 'Webhook processed successfully'}), 200
        
    except Exception as e:
        logger.error("Failed to process alert webhook", error=str(e))
        return jsonify({'error': str(e)}), 500