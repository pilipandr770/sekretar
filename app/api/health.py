"""
Health Check API Endpoints

This module provides health check endpoints for monitoring service availability
and system health status.
"""
import logging
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.service_health_monitor import get_service_health_monitor
from app.utils.response import success_response, error_response
from app.utils.auth import admin_required


logger = logging.getLogger(__name__)

health_bp = Blueprint('health', __name__)


@health_bp.route('/health', methods=['GET'])
def health_check():
    """
    Basic health check endpoint.
    
    Returns overall system health status without requiring authentication.
    This endpoint is designed for load balancers and monitoring systems.
    """
    try:
        monitor = get_service_health_monitor()
        overall_health = monitor.get_overall_health()
        
        # Return appropriate HTTP status code based on health
        status_code = 200 if overall_health['healthy'] else 503
        
        return jsonify({
            'status': overall_health['status'],
            'healthy': overall_health['healthy'],
            'timestamp': overall_health.get('last_check'),
            'uptime_seconds': overall_health['uptime_seconds'],
            'services': {
                'total': overall_health['total_services'],
                'healthy': overall_health['healthy_services'],
                'unhealthy': overall_health['unhealthy_services']
            }
        }), status_code
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'healthy': False,
            'error': 'Health check system unavailable'
        }), 503


@health_bp.route('/health/detailed', methods=['GET'])
@jwt_required()
def detailed_health_check():
    """
    Detailed health check endpoint with authentication.
    
    Returns comprehensive health information including individual service status,
    response times, and error messages.
    """
    try:
        monitor = get_service_health_monitor()
        
        overall_health = monitor.get_overall_health()
        service_status = monitor.get_service_status()
        feature_flags = monitor.get_feature_flags()
        
        return success_response(
            data={
                'overall': overall_health,
                'services': service_status,
                'features': feature_flags,
                'monitoring_active': overall_health['monitoring_active']
            },
            message="Detailed health check completed"
        )
        
    except Exception as e:
        logger.error(f"Detailed health check failed: {e}")
        return error_response(
            error_code="HEALTH_CHECK_FAILED",
            message="Failed to retrieve detailed health information",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/services', methods=['GET'])
@jwt_required()
def services_health():
    """
    Get health status of all monitored services.
    
    Returns detailed information about each monitored service including
    status, response times, and metadata.
    """
    try:
        monitor = get_service_health_monitor()
        service_status = monitor.get_service_status()
        
        return success_response(
            data=service_status,
            message="Service health status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Services health check failed: {e}")
        return error_response(
            error_code="SERVICES_HEALTH_FAILED",
            message="Failed to retrieve service health status",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/services/<service_name>', methods=['GET'])
@jwt_required()
def service_health(service_name):
    """
    Get health status of a specific service.
    
    Args:
        service_name: Name of the service to check
    """
    try:
        monitor = get_service_health_monitor()
        service_status = monitor.get_service_status()
        
        if service_name not in service_status:
            return error_response(
                error_code="SERVICE_NOT_FOUND",
                message=f"Service '{service_name}' not found",
                status_code=404
            )
        
        # Perform immediate health check if requested
        if request.args.get('refresh', '').lower() == 'true':
            is_healthy = monitor.check_service_health(service_name)
            service_status = monitor.get_service_status()
        
        return success_response(
            data=service_status[service_name],
            message=f"Health status for service '{service_name}' retrieved"
        )
        
    except Exception as e:
        logger.error(f"Service health check failed for {service_name}: {e}")
        return error_response(
            error_code="SERVICE_HEALTH_FAILED",
            message=f"Failed to retrieve health status for service '{service_name}'",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/features', methods=['GET'])
@jwt_required()
def feature_flags():
    """
    Get current feature flags based on service availability.
    
    Returns feature flags that indicate which application features
    are currently available based on service health.
    """
    try:
        monitor = get_service_health_monitor()
        features = monitor.get_feature_flags()
        
        return success_response(
            data=features,
            message="Feature flags retrieved"
        )
        
    except Exception as e:
        logger.error(f"Feature flags retrieval failed: {e}")
        return error_response(
            error_code="FEATURE_FLAGS_FAILED",
            message="Failed to retrieve feature flags",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/features/<feature_name>', methods=['GET'])
@jwt_required()
def feature_status(feature_name):
    """
    Check if a specific feature is enabled.
    
    Args:
        feature_name: Name of the feature to check
    """
    try:
        monitor = get_service_health_monitor()
        is_enabled = monitor.is_feature_enabled(feature_name)
        
        return success_response(
            data={
                'feature': feature_name,
                'enabled': is_enabled
            },
            message=f"Feature '{feature_name}' status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Feature status check failed for {feature_name}: {e}")
        return error_response(
            error_code="FEATURE_STATUS_FAILED",
            message=f"Failed to check status for feature '{feature_name}'",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/features/<feature_name>', methods=['POST'])
@jwt_required()
@admin_required
def toggle_feature(feature_name):
    """
    Manually toggle a feature flag (admin only).
    
    Args:
        feature_name: Name of the feature to toggle
    """
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled')
        
        if enabled is None:
            return error_response(
                error_code="MISSING_ENABLED_PARAMETER",
                message="Missing 'enabled' parameter in request body",
                status_code=400
            )
        
        monitor = get_service_health_monitor()
        
        if enabled:
            monitor.enable_feature(feature_name)
        else:
            monitor.disable_feature(feature_name)
        
        return success_response(
            data={
                'feature': feature_name,
                'enabled': enabled
            },
            message=f"Feature '{feature_name}' {'enabled' if enabled else 'disabled'}"
        )
        
    except Exception as e:
        logger.error(f"Feature toggle failed for {feature_name}: {e}")
        return error_response(
            error_code="FEATURE_TOGGLE_FAILED",
            message=f"Failed to toggle feature '{feature_name}'",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/monitoring', methods=['GET'])
@jwt_required()
@admin_required
def monitoring_status():
    """
    Get health monitoring system status (admin only).
    
    Returns information about the health monitoring system itself,
    including statistics and configuration.
    """
    try:
        monitor = get_service_health_monitor()
        overall_health = monitor.get_overall_health()
        
        # Get additional monitoring details
        monitoring_info = {
            'active': overall_health['monitoring_active'],
            'uptime_seconds': overall_health['uptime_seconds'],
            'statistics': overall_health['statistics'],
            'last_check': overall_health['last_check'],
            'services_monitored': overall_health['total_services'],
            'check_interval': current_app.config.get('HEALTH_CHECK_INTERVAL', 30),
            'timeout': current_app.config.get('HEALTH_CHECK_TIMEOUT', 5)
        }
        
        return success_response(
            data=monitoring_info,
            message="Health monitoring status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Monitoring status retrieval failed: {e}")
        return error_response(
            error_code="MONITORING_STATUS_FAILED",
            message="Failed to retrieve monitoring status",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/monitoring/start', methods=['POST'])
@jwt_required()
@admin_required
def start_monitoring():
    """
    Start health monitoring (admin only).
    
    Starts the background health monitoring system if it's not already running.
    """
    try:
        monitor = get_service_health_monitor()
        monitor.start_monitoring()
        
        return success_response(
            message="Health monitoring started"
        )
        
    except Exception as e:
        logger.error(f"Failed to start monitoring: {e}")
        return error_response(
            error_code="START_MONITORING_FAILED",
            message="Failed to start health monitoring",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/monitoring/stop', methods=['POST'])
@jwt_required()
@admin_required
def stop_monitoring():
    """
    Stop health monitoring (admin only).
    
    Stops the background health monitoring system.
    """
    try:
        monitor = get_service_health_monitor()
        monitor.stop_monitoring()
        
        return success_response(
            message="Health monitoring stopped"
        )
        
    except Exception as e:
        logger.error(f"Failed to stop monitoring: {e}")
        return error_response(
            error_code="STOP_MONITORING_FAILED",
            message="Failed to stop health monitoring",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/check/<service_name>', methods=['POST'])
@jwt_required()
@admin_required
def force_service_check(service_name):
    """
    Force an immediate health check for a specific service (admin only).
    
    Args:
        service_name: Name of the service to check
    """
    try:
        monitor = get_service_health_monitor()
        
        # Perform immediate health check
        is_healthy = monitor.check_service_health(service_name)
        service_status = monitor.get_service_status()
        
        if service_name not in service_status:
            return error_response(
                error_code="SERVICE_NOT_FOUND",
                message=f"Service '{service_name}' not found",
                status_code=404
            )
        
        return success_response(
            data=service_status[service_name],
            message=f"Forced health check completed for service '{service_name}'"
        )
        
    except Exception as e:
        logger.error(f"Forced service check failed for {service_name}: {e}")
        return error_response(
            error_code="FORCED_CHECK_FAILED",
            message=f"Failed to perform forced health check for service '{service_name}'",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/readiness', methods=['GET'])
def readiness_check():
    """
    Kubernetes-style readiness check.
    
    Returns 200 if the application is ready to serve requests,
    503 if critical services are unavailable.
    """
    try:
        monitor = get_service_health_monitor()
        overall_health = monitor.get_overall_health()
        
        # Check if any critical services are unhealthy
        if overall_health['critical_unhealthy'] > 0:
            return jsonify({
                'ready': False,
                'reason': 'Critical services unavailable'
            }), 503
        
        return jsonify({
            'ready': True,
            'status': overall_health['status']
        }), 200
        
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return jsonify({
            'ready': False,
            'reason': 'Health check system unavailable'
        }), 503


@health_bp.route('/liveness', methods=['GET'])
def liveness_check():
    """
    Kubernetes-style liveness check.
    
    Returns 200 if the application is alive and running,
    regardless of service availability.
    """
    try:
        # Simple check that the application is responsive
        return jsonify({
            'alive': True,
            'timestamp': current_app.config.get('BUILD_DATE', 'unknown')
        }), 200
        
    except Exception as e:
        logger.error(f"Liveness check failed: {e}")
        return jsonify({
            'alive': False,
            'error': str(e)
        }), 500


# Error handlers for health blueprint
@health_bp.errorhandler(404)
def health_not_found(error):
    """Handle 404 errors in health endpoints."""
    return error_response(
        error_code="HEALTH_ENDPOINT_NOT_FOUND",
        message="Health endpoint not found",
        status_code=404
    )


@health_bp.errorhandler(500)
def health_internal_error(error):
    """Handle 500 errors in health endpoints."""
    return error_response(
        error_code="HEALTH_INTERNAL_ERROR",
        message="Internal error in health check system",
        status_code=500
    )