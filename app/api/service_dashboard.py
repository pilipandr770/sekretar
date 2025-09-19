"""
Service Status Dashboard API

Provides endpoints for service health monitoring dashboard with real-time status,
metrics, and management capabilities.
"""

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from datetime import datetime, timedelta
from typing import Dict, Any, List
from app.utils.response import success_response, error_response
from app.services.service_health_monitor import service_health_monitor, ServiceStatus
from app.services.health_service import HealthService
from app.services.monitoring_service import monitoring_service
from app.services.alerting_service import alerting_service
import structlog

logger = structlog.get_logger()

# Create blueprint
service_dashboard_bp = Blueprint('service_dashboard', __name__)


@service_dashboard_bp.route('/status', methods=['GET'])
def get_service_status():
    """Get overall service status (public endpoint)."""
    try:
        # Get overall health from existing health service
        health_result = HealthService.get_overall_health()
        
        # Get enhanced status from service health monitor
        enhanced_status = service_health_monitor.get_all_services_status()
        
        # Combine results
        status_data = {
            "overall_status": enhanced_status.get("overall_status", health_result.status),
            "timestamp": health_result.timestamp,
            "services": {},
            "summary": {
                "total_services": enhanced_status.get("total_services", len(health_result.checks)),
                "healthy_services": enhanced_status.get("healthy_services", 0),
                "degraded_services": enhanced_status.get("degraded_services", 0),
                "unhealthy_services": enhanced_status.get("unhealthy_services", 0)
            }
        }
        
        # Add service details
        for service_name, check_result in health_result.checks.items():
            enhanced_service = enhanced_status.get("services", {}).get(service_name, {})
            
            status_data["services"][service_name] = {
                "status": enhanced_service.get("status", check_result.status),
                "response_time_ms": enhanced_service.get("response_time_ms", check_result.response_time_ms),
                "error_message": enhanced_service.get("error_message", check_result.error),
                "uptime_percentage": enhanced_service.get("uptime_percentage", 100.0),
                "last_check": enhanced_service.get("last_check", datetime.utcnow().isoformat())
            }
        
        # Determine HTTP status code
        status_code = 200
        if status_data["overall_status"] == "unhealthy":
            status_code = 503
        elif status_data["overall_status"] == "degraded":
            status_code = 200  # Still operational but with issues
        
        return success_response(
            message="Service status retrieved successfully",
            data=status_data,
            status_code=status_code
        )
        
    except Exception as e:
        logger.error("Failed to get service status", error=str(e))
        return error_response(
            error_code="SERVICE_STATUS_ERROR",
            message="Failed to retrieve service status",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/status/detailed', methods=['GET'])
@jwt_required()
def get_detailed_service_status():
    """Get detailed service status with metrics (authenticated endpoint)."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for detailed service status',
                status_code=401
            )
        
        # Get comprehensive service status
        enhanced_status = service_health_monitor.get_all_services_status()
        
        # Get system metrics if monitoring service is available
        system_metrics = {}
        if monitoring_service._initialized:
            metrics_summary = monitoring_service.get_metrics_summary()
            if "error" not in metrics_summary:
                system_metrics = metrics_summary
        
        # Get active alerts
        active_alerts = []
        try:
            alerts = alerting_service.get_active_alerts()
            active_alerts = [alert.to_dict() for alert in alerts]
        except Exception as e:
            logger.warning("Failed to get active alerts", error=str(e))
        
        detailed_status = {
            "overall_status": enhanced_status.get("overall_status", "unknown"),
            "services": enhanced_status.get("services", {}),
            "summary": {
                "total_services": enhanced_status.get("total_services", 0),
                "healthy_services": enhanced_status.get("healthy_services", 0),
                "degraded_services": enhanced_status.get("degraded_services", 0),
                "unhealthy_services": enhanced_status.get("unhealthy_services", 0)
            },
            "system_metrics": system_metrics,
            "active_alerts": active_alerts,
            "monitoring": {
                "enabled": service_health_monitor.monitoring_enabled,
                "check_interval": service_health_monitor.check_interval,
                "last_updated": enhanced_status.get("last_updated")
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return success_response(
            message="Detailed service status retrieved successfully",
            data=detailed_status
        )
        
    except Exception as e:
        logger.error("Failed to get detailed service status", error=str(e))
        return error_response(
            error_code="DETAILED_SERVICE_STATUS_ERROR",
            message="Failed to retrieve detailed service status",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/services/<service_name>/status', methods=['GET'])
@jwt_required()
def get_service_details(service_name: str):
    """Get detailed status for a specific service."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for service details',
                status_code=401
            )
        
        # Get service status
        service_status = service_health_monitor.get_service_status(service_name)
        
        if "error" in service_status:
            return error_response(
                error_code="SERVICE_NOT_FOUND",
                message=service_status["error"],
                status_code=404
            )
        
        # Get service history
        service_history = service_health_monitor.get_service_history(service_name, limit=100)
        
        # Get service-specific metrics
        service_metrics = {}
        if monitoring_service._initialized:
            try:
                service_metrics = monitoring_service.get_endpoint_metrics(service_name)
            except Exception as e:
                logger.warning("Failed to get service metrics", service=service_name, error=str(e))
        
        service_details = {
            "service": service_status,
            "history": service_history,
            "metrics": service_metrics,
            "recovery_actions": len(service_health_monitor.recovery_actions.get(service_name, [])),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return success_response(
            message=f"Service details for {service_name} retrieved successfully",
            data=service_details
        )
        
    except Exception as e:
        logger.error("Failed to get service details", service=service_name, error=str(e))
        return error_response(
            error_code="SERVICE_DETAILS_ERROR",
            message=f"Failed to retrieve details for service {service_name}",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/services/<service_name>/history', methods=['GET'])
@jwt_required()
def get_service_history(service_name: str):
    """Get health history for a specific service."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for service history',
                status_code=401
            )
        
        # Get query parameters
        limit = request.args.get('limit', 50, type=int)
        hours = request.args.get('hours', 24, type=int)
        
        # Validate limits
        limit = min(limit, 1000)  # Max 1000 records
        hours = min(hours, 168)   # Max 1 week
        
        # Get service history
        history = service_health_monitor.get_service_history(service_name, limit=limit)
        
        # Filter by time range if specified
        if hours < 168:  # Only filter if less than max
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            history = [
                record for record in history
                if datetime.fromisoformat(record['timestamp']) >= cutoff_time
            ]
        
        # Calculate statistics
        total_records = len(history)
        healthy_records = sum(1 for r in history if r['status'] == 'healthy')
        degraded_records = sum(1 for r in history if r['status'] == 'degraded')
        unhealthy_records = sum(1 for r in history if r['status'] == 'unhealthy')
        
        uptime_percentage = (healthy_records / total_records * 100) if total_records > 0 else 0
        
        # Calculate average response time
        response_times = [r['response_time_ms'] for r in history if r['response_time_ms'] is not None]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        history_data = {
            "service_name": service_name,
            "timeframe_hours": hours,
            "total_records": total_records,
            "statistics": {
                "uptime_percentage": round(uptime_percentage, 2),
                "healthy_checks": healthy_records,
                "degraded_checks": degraded_records,
                "unhealthy_checks": unhealthy_records,
                "average_response_time_ms": round(avg_response_time, 2)
            },
            "history": history,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return success_response(
            message=f"Service history for {service_name} retrieved successfully",
            data=history_data
        )
        
    except Exception as e:
        logger.error("Failed to get service history", service=service_name, error=str(e))
        return error_response(
            error_code="SERVICE_HISTORY_ERROR",
            message=f"Failed to retrieve history for service {service_name}",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/services/<service_name>/check', methods=['POST'])
@jwt_required()
def trigger_service_check(service_name: str):
    """Manually trigger a health check for a specific service."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required to trigger service checks',
                status_code=401
            )
        
        # Check if service exists
        if service_name not in service_health_monitor.services:
            return error_response(
                error_code="SERVICE_NOT_FOUND",
                message=f"Service {service_name} not found",
                status_code=404
            )
        
        # Trigger health check
        logger.info("Manual health check triggered", service=service_name, user=current_user)
        metrics = service_health_monitor.check_service_health(service_name)
        
        check_result = {
            "service_name": service_name,
            "status": metrics.status.value,
            "response_time_ms": metrics.response_time_ms,
            "error_message": metrics.error_message,
            "check_time": metrics.last_check.isoformat(),
            "triggered_by": current_user
        }
        
        return success_response(
            message=f"Health check triggered for {service_name}",
            data=check_result
        )
        
    except Exception as e:
        logger.error("Failed to trigger service check", service=service_name, error=str(e))
        return error_response(
            error_code="SERVICE_CHECK_ERROR",
            message=f"Failed to trigger health check for service {service_name}",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/alerts', methods=['GET'])
@jwt_required()
def get_service_alerts():
    """Get service-related alerts."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for service alerts',
                status_code=401
            )
        
        # Get query parameters
        status = request.args.get('status', 'active')  # active, resolved, all
        limit = request.args.get('limit', 50, type=int)
        
        # Get alerts
        if status == 'active':
            alerts = alerting_service.get_active_alerts()
        elif status == 'all':
            alerts = alerting_service.get_alert_history(limit=limit)
        else:
            # Filter resolved alerts
            all_alerts = alerting_service.get_alert_history(limit=limit * 2)
            alerts = [alert for alert in all_alerts if alert.status.value == status][:limit]
        
        # Filter service-related alerts
        service_alerts = [
            alert for alert in alerts
            if alert.source in ['service_health_monitor', 'health_service'] or
            'service' in alert.labels
        ]
        
        # Convert to dict format
        alerts_data = [alert.to_dict() for alert in service_alerts]
        
        alert_summary = {
            "total_alerts": len(alerts_data),
            "status_filter": status,
            "alerts": alerts_data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return success_response(
            message="Service alerts retrieved successfully",
            data=alert_summary
        )
        
    except Exception as e:
        logger.error("Failed to get service alerts", error=str(e))
        return error_response(
            error_code="SERVICE_ALERTS_ERROR",
            message="Failed to retrieve service alerts",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/monitoring/config', methods=['GET'])
@jwt_required()
def get_monitoring_config():
    """Get current monitoring configuration."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for monitoring configuration',
                status_code=401
            )
        
        config_data = {
            "monitoring_enabled": service_health_monitor.monitoring_enabled,
            "check_interval_seconds": service_health_monitor.check_interval,
            "notification_cooldown_seconds": service_health_monitor.notification_cooldown,
            "registered_services": list(service_health_monitor.services.keys()),
            "recovery_actions": {
                service: len(actions) 
                for service, actions in service_health_monitor.recovery_actions.items()
            },
            "alerting_enabled": current_app.config.get('ALERTING_ENABLED', True),
            "health_check_settings": {
                "database_enabled": current_app.config.get('HEALTH_CHECK_DATABASE_ENABLED', True),
                "redis_enabled": current_app.config.get('HEALTH_CHECK_REDIS_ENABLED', True),
                "timeout_seconds": current_app.config.get('HEALTH_CHECK_TIMEOUT', 5)
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return success_response(
            message="Monitoring configuration retrieved successfully",
            data=config_data
        )
        
    except Exception as e:
        logger.error("Failed to get monitoring configuration", error=str(e))
        return error_response(
            error_code="MONITORING_CONFIG_ERROR",
            message="Failed to retrieve monitoring configuration",
            status_code=500,
            details=str(e)
        )


@service_dashboard_bp.route('/monitoring/config', methods=['PUT'])
@jwt_required()
def update_monitoring_config():
    """Update monitoring configuration."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required to update monitoring configuration',
                status_code=401
            )
        
        data = request.get_json()
        if not data:
            return error_response(
                error_code='VALIDATION_ERROR',
                message='Request body is required',
                status_code=400
            )
        
        # Update configuration
        updated_fields = []
        
        if 'monitoring_enabled' in data:
            service_health_monitor.monitoring_enabled = bool(data['monitoring_enabled'])
            updated_fields.append('monitoring_enabled')
        
        if 'check_interval_seconds' in data:
            interval = int(data['check_interval_seconds'])
            if 10 <= interval <= 3600:  # Between 10 seconds and 1 hour
                service_health_monitor.check_interval = interval
                updated_fields.append('check_interval_seconds')
        
        if 'notification_cooldown_seconds' in data:
            cooldown = int(data['notification_cooldown_seconds'])
            if 60 <= cooldown <= 7200:  # Between 1 minute and 2 hours
                service_health_monitor.notification_cooldown = cooldown
                updated_fields.append('notification_cooldown_seconds')
        
        logger.info("Monitoring configuration updated", 
                   user=current_user, fields=updated_fields)
        
        return success_response(
            message="Monitoring configuration updated successfully",
            data={
                "updated_fields": updated_fields,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
    except Exception as e:
        logger.error("Failed to update monitoring configuration", error=str(e))
        return error_response(
            error_code="MONITORING_CONFIG_UPDATE_ERROR",
            message="Failed to update monitoring configuration",
            status_code=500,
            details=str(e)
        )


# Error handlers
@service_dashboard_bp.errorhandler(404)
def not_found(error):
    """Handle 404 errors."""
    return error_response(
        error_code="ENDPOINT_NOT_FOUND",
        message="Service dashboard endpoint not found",
        status_code=404
    )


@service_dashboard_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 errors."""
    return error_response(
        error_code="INTERNAL_SERVER_ERROR",
        message="Internal server error in service dashboard",
        status_code=500
    )