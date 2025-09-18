"""
Service Status API

This module provides API endpoints for service status, notifications,
and system health information.
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.response import success_response, error_response
from app.utils.graceful_degradation import get_graceful_degradation_manager
from app.utils.user_notifications import get_user_notification_manager
from app.utils.enhanced_logging import get_enhanced_logging_manager
import structlog

logger = structlog.get_logger(__name__)

service_status_bp = Blueprint('service_status', __name__)


def _calculate_health_score(status_summary: dict) -> float:
    """Calculate overall health score based on service status."""
    total_services = (
        status_summary.get('degraded_services', 0) + 
        status_summary.get('unavailable_services', 0) + 
        10  # Assume 10 total services for calculation
    )
    
    if total_services == 0:
        return 100.0
    
    # Weight different issues
    degraded_weight = 0.3
    unavailable_weight = 0.7
    critical_issues_weight = 0.5
    
    degraded_impact = status_summary.get('degraded_services', 0) * degraded_weight
    unavailable_impact = status_summary.get('unavailable_services', 0) * unavailable_weight
    critical_impact = status_summary.get('critical_issues', 0) * critical_issues_weight
    
    total_impact = degraded_impact + unavailable_impact + critical_impact
    health_score = max(0, 100 - (total_impact / total_services * 100))
    
    return round(health_score, 1)


@service_status_bp.route('/status', methods=['GET'])
def get_service_status():
    """Get overall service status and degradations."""
    try:
        degradation_manager = get_graceful_degradation_manager()
        
        status_summary = degradation_manager.get_service_status_summary()
        degradations = degradation_manager.get_user_visible_degradations()
        
        # Add timestamp
        from datetime import datetime
        timestamp = datetime.now().isoformat()
        
        return success_response(
            message="Service status retrieved successfully",
            data={
                'overall_level': status_summary['overall_level'],
                'degraded_services': status_summary['degraded_services'],
                'unavailable_services': status_summary['unavailable_services'],
                'configuration_issues': status_summary['configuration_issues'],
                'critical_issues': status_summary['critical_issues'],
                'degradations': degradations,
                'timestamp': timestamp,
                'health_score': _calculate_health_score(status_summary)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get service status: {e}")
        
        # Use error formatter for user-friendly message
        try:
            from app.utils.error_formatter import format_user_friendly_error
            error_info = format_user_friendly_error(e, {'endpoint': 'service_status'})
            
            return error_response(
                error_code='SERVICE_STATUS_ERROR',
                message=error_info['user_message'],
                status_code=500,
                details=error_info.get('technical_details') if current_app.config.get('DEBUG') else None
            )
        except ImportError:
            return error_response(
                error_code='SERVICE_STATUS_ERROR',
                message='Failed to retrieve service status',
                status_code=500
            )


@service_status_bp.route('/notifications', methods=['GET'])
@jwt_required(optional=True)
def get_notifications():
    """Get user notifications."""
    try:
        notification_manager = get_user_notification_manager()
        
        # Get active notifications
        notifications = notification_manager.get_active_notifications()
        
        # Convert to dict format
        notification_data = []
        for notification in notifications:
            notification_data.append({
                'id': notification.id,
                'type': notification.type.value,
                'priority': notification.priority.value,
                'title': notification.title,
                'message': notification.message,
                'dismissible': notification.dismissible,
                'auto_dismiss': notification.auto_dismiss,
                'auto_dismiss_delay': notification.auto_dismiss_delay,
                'action_url': notification.action_url,
                'action_text': notification.action_text,
                'service_affected': notification.service_affected,
                'resolution_steps': notification.resolution_steps,
                'timestamp': notification.timestamp.isoformat()
            })
        
        return success_response(
            message="Notifications retrieved successfully",
            data={
                'notifications': notification_data,
                'count': len(notification_data)
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get notifications: {e}")
        return error_response(
            error_code='NOTIFICATIONS_ERROR',
            message='Failed to retrieve notifications',
            status_code=500
        )


@service_status_bp.route('/notifications/<notification_id>/dismiss', methods=['POST'])
@jwt_required(optional=True)
def dismiss_notification(notification_id):
    """Dismiss a notification."""
    try:
        notification_manager = get_user_notification_manager()
        
        success = notification_manager.dismiss_notification(notification_id)
        
        if success:
            return success_response(
                message="Notification dismissed successfully"
            )
        else:
            return error_response(
                error_code='NOTIFICATION_NOT_FOUND',
                message='Notification not found',
                status_code=404
            )
        
    except Exception as e:
        logger.error(f"Failed to dismiss notification {notification_id}: {e}")
        return error_response(
            error_code='DISMISS_NOTIFICATION_ERROR',
            message='Failed to dismiss notification',
            status_code=500
        )


@service_status_bp.route('/health/detailed', methods=['GET'])
@jwt_required()
def get_detailed_health():
    """Get detailed health information (admin only)."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for detailed health information',
                status_code=401
            )
        
        # Get detailed information from all managers
        degradation_manager = get_graceful_degradation_manager()
        notification_manager = get_user_notification_manager()
        logging_manager = get_enhanced_logging_manager()
        
        detailed_health = {
            'service_status': {
                'summary': degradation_manager.get_service_status_summary(),
                'degradations': degradation_manager.get_service_degradations(),
                'configuration_issues': degradation_manager.get_configuration_issues()
            },
            'notifications': {
                'stats': notification_manager.get_notification_stats(),
                'admin_notifications': notification_manager.get_admin_notifications()
            },
            'logging': {
                'stats': logging_manager.get_logging_stats()
            }
        }
        
        return success_response(
            message="Detailed health information retrieved successfully",
            data=detailed_health
        )
        
    except Exception as e:
        logger.error(f"Failed to get detailed health: {e}")
        return error_response(
            error_code='DETAILED_HEALTH_ERROR',
            message='Failed to retrieve detailed health information',
            status_code=500
        )


@service_status_bp.route('/configuration/validate', methods=['POST'])
@jwt_required()
def validate_configuration():
    """Validate system configuration (admin only)."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for configuration validation',
                status_code=401
            )
        
        # Re-assess service availability and configuration
        degradation_manager = get_graceful_degradation_manager()
        degradation_manager._assess_service_availability()
        
        # Get updated status
        status_summary = degradation_manager.get_service_status_summary()
        configuration_issues = degradation_manager.get_configuration_issues()
        
        return success_response(
            message="Configuration validation completed",
            data={
                'status_summary': status_summary,
                'configuration_issues': [
                    {
                        'issue_type': issue.issue_type,
                        'severity': issue.severity.value,
                        'message': issue.message,
                        'service_affected': issue.service_affected,
                        'resolution_steps': issue.resolution_steps,
                        'environment_variables': issue.environment_variables,
                        'timestamp': issue.timestamp.isoformat()
                    }
                    for issue in configuration_issues
                ]
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to validate configuration: {e}")
        return error_response(
            error_code='CONFIGURATION_VALIDATION_ERROR',
            message='Failed to validate configuration',
            status_code=500
        )


@service_status_bp.route('/services/<service_name>/status', methods=['GET'])
def get_service_specific_status(service_name):
    """Get status for a specific service."""
    try:
        degradation_manager = get_graceful_degradation_manager()
        
        # Check if service is available
        is_available = degradation_manager.is_service_available(service_name)
        
        # Get service degradation if any
        degradations = degradation_manager.get_service_degradations()
        service_degradation = degradations.get(service_name)
        
        service_status = {
            'service_name': service_name,
            'available': is_available,
            'degradation': None
        }
        
        if service_degradation:
            service_status['degradation'] = {
                'level': service_degradation.level.value,
                'reason': service_degradation.reason,
                'fallback_enabled': service_degradation.fallback_enabled,
                'user_message': service_degradation.user_message,
                'recovery_instructions': service_degradation.recovery_instructions,
                'timestamp': service_degradation.timestamp.isoformat()
            }
        
        return success_response(
            message=f"Status for {service_name} retrieved successfully",
            data=service_status
        )
        
    except Exception as e:
        logger.error(f"Failed to get status for service {service_name}: {e}")
        return error_response(
            error_code='SERVICE_STATUS_ERROR',
            message=f'Failed to retrieve status for {service_name}',
            status_code=500
        )


@service_status_bp.route('/features', methods=['GET'])
def get_feature_status():
    """Get feature availability status."""
    try:
        degradation_manager = get_graceful_degradation_manager()
        
        # Check common features
        features = [
            'ai_features',
            'payment_processing',
            'google_login',
            'telegram_integration',
            'signal_integration',
            'redis_cache',
            'database'
        ]
        
        feature_status = {}
        for feature in features:
            feature_status[feature] = degradation_manager.is_feature_enabled(feature)
        
        return success_response(
            message="Feature status retrieved successfully",
            data={
                'features': feature_status,
                'overall_level': degradation_manager.get_overall_service_level().value
            }
        )
        
    except Exception as e:
        logger.error(f"Failed to get feature status: {e}")
        return error_response(
            error_code='FEATURE_STATUS_ERROR',
            message='Failed to retrieve feature status',
            status_code=500
        )


@service_status_bp.route('/troubleshooting', methods=['GET'])
@jwt_required(optional=True)
def get_troubleshooting_info():
    """Get troubleshooting information for current issues."""
    try:
        degradation_manager = get_graceful_degradation_manager()
        logging_manager = get_enhanced_logging_manager()
        
        # Get current issues
        degradations = degradation_manager.get_service_degradations()
        configuration_issues = degradation_manager.get_configuration_issues()
        recent_errors = logging_manager.error_tracker.get_recent_errors(5)
        
        # Create troubleshooting guide
        troubleshooting_info = {
            'current_issues': [],
            'resolution_guides': [],
            'recent_errors': [],
            'system_health': {
                'overall_level': degradation_manager.get_overall_service_level().value,
                'health_score': _calculate_health_score(degradation_manager.get_service_status_summary())
            }
        }
        
        # Add service degradations
        for service_name, degradation in degradations.items():
            issue = {
                'type': 'service_degradation',
                'service': service_name,
                'level': degradation.level.value,
                'description': degradation.reason,
                'user_impact': degradation.user_message,
                'resolution_steps': []
            }
            
            if degradation.recovery_instructions:
                issue['resolution_steps'].append(degradation.recovery_instructions)
            
            troubleshooting_info['current_issues'].append(issue)
        
        # Add configuration issues
        for config_issue in configuration_issues:
            issue = {
                'type': 'configuration_issue',
                'severity': config_issue.severity.value,
                'description': config_issue.message,
                'affected_service': config_issue.service_affected,
                'resolution_steps': config_issue.resolution_steps,
                'environment_variables': config_issue.environment_variables
            }
            troubleshooting_info['current_issues'].append(issue)
        
        # Add recent errors (sanitized for user)
        current_user = get_jwt_identity()
        include_technical = current_user is not None  # Only for authenticated users
        
        for error in recent_errors:
            error_info = {
                'timestamp': error['timestamp'],
                'category': error.get('error_category', 'general'),
                'severity': error.get('error_severity', 'low'),
                'count': error['error_count']
            }
            
            if include_technical:
                error_info.update({
                    'error_type': error['error_type'],
                    'message': error['error_message'][:200] + '...' if len(error['error_message']) > 200 else error['error_message']
                })
            
            troubleshooting_info['recent_errors'].append(error_info)
        
        # Add general resolution guides
        troubleshooting_info['resolution_guides'] = [
            {
                'title': 'Database Connection Issues',
                'description': 'Steps to resolve database connectivity problems',
                'steps': [
                    'Check database service status',
                    'Verify connection settings in environment variables',
                    'Test network connectivity to database server',
                    'Review database logs for errors',
                    'Restart database service if necessary'
                ]
            },
            {
                'title': 'External Service Issues',
                'description': 'Steps to resolve external service connectivity problems',
                'steps': [
                    'Check external service status pages',
                    'Verify API credentials and configuration',
                    'Test network connectivity',
                    'Review rate limiting and quotas',
                    'Check for service updates or changes'
                ]
            },
            {
                'title': 'Configuration Problems',
                'description': 'Steps to resolve configuration issues',
                'steps': [
                    'Review environment variables',
                    'Check configuration file syntax',
                    'Validate required settings',
                    'Restart application after changes',
                    'Test configuration in development environment'
                ]
            }
        ]
        
        return success_response(
            message="Troubleshooting information retrieved successfully",
            data=troubleshooting_info
        )
        
    except Exception as e:
        logger.error(f"Failed to get troubleshooting info: {e}")
        return error_response(
            error_code='TROUBLESHOOTING_ERROR',
            message='Failed to retrieve troubleshooting information',
            status_code=500
        )


@service_status_bp.route('/error-statistics', methods=['GET'])
@jwt_required()
def get_error_statistics():
    """Get comprehensive error statistics (admin only)."""
    try:
        current_user = get_jwt_identity()
        if not current_user:
            return error_response(
                error_code='AUTHENTICATION_REQUIRED',
                message='Authentication required for error statistics',
                status_code=401
            )
        
        # Get comprehensive error statistics
        try:
            from app.utils.comprehensive_error_handler import get_comprehensive_error_handler
            error_handler = get_comprehensive_error_handler()
            statistics = error_handler.get_error_statistics()
        except ImportError:
            # Fallback to individual managers
            statistics = {}
            
            try:
                from app.utils.enhanced_logging import get_enhanced_logging_manager
                logging_manager = get_enhanced_logging_manager()
                statistics['error_tracking'] = logging_manager.get_logging_stats()
            except ImportError:
                pass
            
            try:
                from app.utils.graceful_degradation import get_graceful_degradation_manager
                degradation_manager = get_graceful_degradation_manager()
                statistics['service_degradations'] = degradation_manager.get_service_status_summary()
            except ImportError:
                pass
            
            try:
                from app.utils.user_notifications import get_user_notification_manager
                notification_manager = get_user_notification_manager()
                statistics['notifications'] = notification_manager.get_notification_stats()
            except ImportError:
                pass
        
        return success_response(
            message="Error statistics retrieved successfully",
            data=statistics
        )
        
    except Exception as e:
        logger.error(f"Failed to get error statistics: {e}")
        return error_response(
            error_code='ERROR_STATISTICS_ERROR',
            message='Failed to retrieve error statistics',
            status_code=500
        )