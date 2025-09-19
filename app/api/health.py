"""
Health Check API Endpoints

This module provides health check endpoints for monitoring service availability
and system health status.
"""
import logging
import asyncio
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.service_health_monitor import get_service_health_monitor
from app.utils.response import success_response, error_response
from app.utils.auth import admin_required
from app.services.health_validator import health_validator


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


@health_bp.route('/health/comprehensive', methods=['GET'])
@jwt_required()
@admin_required
def comprehensive_health_check():
    """
    Comprehensive health check with fallback modes and detailed status messages.
    
    This endpoint uses the HealthValidator to check all external services,
    provide fallback information, and give actionable recommendations.
    """
    try:
        # Run comprehensive validation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(health_validator.validate_all_services())
        finally:
            loop.close()
        
        # Generate human-readable summary
        summary = health_validator.generate_status_summary(report)
        
        # Convert dataclasses to dictionaries for JSON serialization
        services_data = {}
        for name, result in report.services.items():
            services_data[name] = {
                'service_name': result.service_name,
                'service_type': result.service_type.value,
                'status': result.status.value,
                'response_time_ms': result.response_time_ms,
                'error_message': result.error_message,
                'fallback_available': result.fallback_available,
                'fallback_message': result.fallback_message,
                'recommendations': result.recommendations,
                'last_checked': result.last_checked.isoformat()
            }
        
        response_data = {
            'overall_status': report.overall_status.value,
            'services': services_data,
            'fallback_services': report.fallback_services,
            'critical_issues': report.critical_issues,
            'warnings': report.warnings,
            'recommendations': report.recommendations,
            'summary': summary,
            'timestamp': report.timestamp.isoformat()
        }
        
        # Return appropriate HTTP status based on overall health
        if report.overall_status.value == 'unavailable':
            status_code = 503
        elif report.overall_status.value in ['degraded', 'fallback']:
            status_code = 200  # Still functional with warnings
        else:
            status_code = 200
        
        return success_response(
            data=response_data,
            message="Comprehensive health check completed"
        ), status_code
        
    except Exception as e:
        logger.error(f"Comprehensive health check failed: {e}")
        return error_response(
            error_code="COMPREHENSIVE_HEALTH_FAILED",
            message="Failed to perform comprehensive health check",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/service/<service_name>/validate', methods=['POST'])
@jwt_required()
@admin_required
def validate_specific_service(service_name):
    """
    Validate a specific external service with fallback information.
    
    Args:
        service_name: Name of the service to validate (openai, stripe, redis, etc.)
    """
    try:
        # Map service names to validation methods
        validation_methods = {
            'database': health_validator.validate_database,
            'redis': health_validator.validate_redis,
            'openai': health_validator.validate_openai,
            'stripe': health_validator.validate_stripe,
            'google_oauth': health_validator.validate_google_oauth,
            'telegram': health_validator.validate_telegram,
            'smtp': health_validator.validate_smtp
        }
        
        if service_name not in validation_methods:
            return error_response(
                error_code="SERVICE_NOT_SUPPORTED",
                message=f"Service '{service_name}' is not supported for validation",
                status_code=400,
                details=f"Supported services: {', '.join(validation_methods.keys())}"
            )
        
        # Run validation for specific service
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(validation_methods[service_name]())
        finally:
            loop.close()
        
        # Generate status message
        status_message = health_validator.get_service_status_message(service_name, result)
        
        response_data = {
            'service_name': result.service_name,
            'service_type': result.service_type.value,
            'status': result.status.value,
            'status_message': status_message,
            'response_time_ms': result.response_time_ms,
            'error_message': result.error_message,
            'fallback_available': result.fallback_available,
            'fallback_message': result.fallback_message,
            'recommendations': result.recommendations,
            'last_checked': result.last_checked.isoformat()
        }
        
        # Return appropriate HTTP status
        if result.status.value == 'unavailable' and not result.fallback_available:
            status_code = 503
        elif result.status.value in ['degraded', 'fallback']:
            status_code = 200  # Still functional with warnings
        else:
            status_code = 200
        
        return success_response(
            data=response_data,
            message=f"Service '{service_name}' validation completed"
        ), status_code
        
    except Exception as e:
        logger.error(f"Service validation failed for {service_name}: {e}")
        return error_response(
            error_code="SERVICE_VALIDATION_FAILED",
            message=f"Failed to validate service '{service_name}'",
            status_code=500,
            details=str(e)
        )


@health_bp.route('/health/fallback-status', methods=['GET'])
@jwt_required()
def get_fallback_status():
    """
    Get current fallback status for all services.
    
    This endpoint provides information about which services are running
    in fallback mode and what functionality is affected.
    """
    try:
        # Run comprehensive validation to get current status
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            report = loop.run_until_complete(health_validator.validate_all_services())
        finally:
            loop.close()
        
        # Extract fallback information
        fallback_info = {}
        for name, result in report.services.items():
            if result.status.value in ['fallback', 'unavailable']:
                fallback_info[name] = {
                    'status': result.status.value,
                    'fallback_available': result.fallback_available,
                    'fallback_message': result.fallback_message,
                    'impact': result.error_message,
                    'recommendations': result.recommendations
                }
        
        response_data = {
            'services_in_fallback': len(report.fallback_services),
            'fallback_services': report.fallback_services,
            'fallback_details': fallback_info,
            'overall_impact': report.overall_status.value,
            'critical_services_down': len(report.critical_issues),
            'timestamp': report.timestamp.isoformat()
        }
        
        return success_response(
            data=response_data,
            message="Fallback status retrieved"
        )
        
    except Exception as e:
        logger.error(f"Fallback status retrieval failed: {e}")
        return error_response(
            error_code="FALLBACK_STATUS_FAILED",
            message="Failed to retrieve fallback status",
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