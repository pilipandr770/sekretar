"""
Health System Initialization

This module initializes and configures the complete health monitoring system
including service monitoring, recovery, alerting, and dashboard components.
"""

from flask import Flask
from app.services.service_health_monitor import init_service_health_monitoring
from app.services.service_recovery import init_service_recovery
from app.services.monitoring_service import init_monitoring
from app.services.alerting_service import init_alerting
import structlog

logger = structlog.get_logger()


def init_complete_health_system(app: Flask):
    """
    Initialize the complete health monitoring system.
    
    This function sets up:
    1. Service health monitoring with automatic checks
    2. Service recovery with intelligent strategies
    3. Performance monitoring and metrics collection
    4. Alerting system with multiple notification channels
    5. Service status dashboard API
    
    Args:
        app: Flask application instance
        
    Returns:
        Dictionary with initialized components
    """
    try:
        logger.info("Initializing complete health monitoring system")
        
        components = {}
        
        # 1. Initialize monitoring service (metrics collection)
        logger.info("Initializing monitoring service")
        monitoring_service = init_monitoring(app)
        components['monitoring'] = monitoring_service
        
        # 2. Initialize alerting service (notifications)
        logger.info("Initializing alerting service")
        alerting_service = init_alerting(app)
        components['alerting'] = alerting_service
        
        # 3. Initialize service recovery system
        logger.info("Initializing service recovery system")
        recovery_manager = init_service_recovery(app)
        components['recovery'] = recovery_manager
        
        # 4. Initialize service health monitoring
        logger.info("Initializing service health monitoring")
        health_monitor = init_service_health_monitoring(app)
        components['health_monitor'] = health_monitor
        
        # 5. Set up health check alert rules
        setup_health_alert_rules(app)
        
        # 6. Configure system-wide health settings
        configure_health_settings(app)
        
        logger.info("Health monitoring system initialization completed successfully")
        
        return {
            'success': True,
            'components': components,
            'message': 'Complete health monitoring system initialized'
        }
        
    except Exception as e:
        logger.error("Failed to initialize health monitoring system", error=str(e))
        return {
            'success': False,
            'error': str(e),
            'message': 'Health monitoring system initialization failed'
        }


def setup_health_alert_rules(app: Flask):
    """Set up health-specific alert rules."""
    try:
        from app.services.alerting_service import alerting_service, AlertRule, AlertSeverity
        from app.services.service_health_monitor import service_health_monitor, ServiceStatus
        
        # Service degradation alert rule
        def check_service_degradation():
            """Check if any service is degraded or unhealthy."""
            try:
                status = service_health_monitor.get_all_services_status()
                degraded_count = status.get('degraded_services', 0)
                unhealthy_count = status.get('unhealthy_services', 0)
                return degraded_count > 0 or unhealthy_count > 0
            except Exception:
                return False
        
        degradation_rule = AlertRule(
            name="service_degradation_detected",
            condition=check_service_degradation,
            severity=AlertSeverity.HIGH,
            message="Service degradation detected",
            description="One or more services are experiencing degradation or are unhealthy",
            labels={"component": "health_system", "type": "service_degradation"},
            cooldown_minutes=10
        )
        alerting_service.add_rule(degradation_rule)
        
        # Multiple service failures alert rule
        def check_multiple_service_failures():
            """Check if multiple services are failing simultaneously."""
            try:
                status = service_health_monitor.get_all_services_status()
                unhealthy_count = status.get('unhealthy_services', 0)
                return unhealthy_count >= 2
            except Exception:
                return False
        
        multiple_failures_rule = AlertRule(
            name="multiple_service_failures",
            condition=check_multiple_service_failures,
            severity=AlertSeverity.CRITICAL,
            message="Multiple service failures detected",
            description="Multiple services are simultaneously unhealthy, indicating a systemic issue",
            labels={"component": "health_system", "type": "systemic_failure"},
            cooldown_minutes=5
        )
        alerting_service.add_rule(multiple_failures_rule)
        
        # Recovery escalation alert rule
        def check_recovery_escalation():
            """Check if any service has escalated recovery attempts."""
            try:
                from app.services.service_recovery import service_recovery_manager
                recovery_status = service_recovery_manager.get_all_recovery_status()
                
                for service_name, status in recovery_status.items():
                    if status.get('escalation_level', 0) >= 2:
                        return True
                return False
            except Exception:
                return False
        
        escalation_rule = AlertRule(
            name="recovery_escalation_high",
            condition=check_recovery_escalation,
            severity=AlertSeverity.HIGH,
            message="Service recovery escalation detected",
            description="Service recovery has escalated to high levels, manual intervention may be required",
            labels={"component": "recovery_system", "type": "escalation"},
            cooldown_minutes=15
        )
        alerting_service.add_rule(escalation_rule)
        
        logger.info("Health alert rules configured successfully")
        
    except Exception as e:
        logger.error("Failed to set up health alert rules", error=str(e))


def configure_health_settings(app: Flask):
    """Configure system-wide health monitoring settings."""
    try:
        # Set health check intervals based on environment
        environment = app.config.get('FLASK_ENV', 'development')
        
        if environment == 'production':
            # More frequent checks in production
            check_interval = 30  # seconds
            notification_cooldown = 300  # 5 minutes
        elif environment == 'testing':
            # Less frequent checks in testing
            check_interval = 120  # 2 minutes
            notification_cooldown = 600  # 10 minutes
        else:
            # Development settings
            check_interval = 60  # 1 minute
            notification_cooldown = 300  # 5 minutes
        
        # Update service health monitor settings
        from app.services.service_health_monitor import service_health_monitor
        service_health_monitor.check_interval = check_interval
        service_health_monitor.notification_cooldown = notification_cooldown
        
        # Configure recovery settings
        from app.services.service_recovery import service_recovery_manager
        service_recovery_manager.recovery_cooldown = notification_cooldown
        
        logger.info("Health system settings configured", 
                   environment=environment,
                   check_interval=check_interval,
                   notification_cooldown=notification_cooldown)
        
    except Exception as e:
        logger.error("Failed to configure health settings", error=str(e))


def get_health_system_status():
    """Get status of all health system components."""
    try:
        from app.services.service_health_monitor import service_health_monitor
        from app.services.service_recovery import service_recovery_manager
        from app.services.monitoring_service import monitoring_service
        from app.services.alerting_service import alerting_service
        
        status = {
            "health_monitor": {
                "enabled": service_health_monitor.monitoring_enabled,
                "services_monitored": len(service_health_monitor.services),
                "check_interval": service_health_monitor.check_interval
            },
            "recovery_manager": {
                "services_with_recovery": len(service_recovery_manager.recovery_strategies),
                "recovery_in_progress": sum(service_recovery_manager.recovery_in_progress.values()),
                "circuit_breakers": len(service_recovery_manager.circuit_breakers)
            },
            "monitoring_service": {
                "initialized": monitoring_service._initialized if hasattr(monitoring_service, '_initialized') else False
            },
            "alerting_service": {
                "rules_configured": len(alerting_service.rules),
                "channels_configured": len(alerting_service.channels),
                "active_alerts": len(alerting_service.active_alerts)
            }
        }
        
        return status
        
    except Exception as e:
        logger.error("Failed to get health system status", error=str(e))
        return {"error": str(e)}


def validate_health_system():
    """Validate that all health system components are working correctly."""
    try:
        validation_results = {
            "overall_valid": True,
            "components": {},
            "issues": [],
            "recommendations": []
        }
        
        # Validate service health monitor
        try:
            from app.services.service_health_monitor import service_health_monitor
            
            if len(service_health_monitor.services) == 0:
                validation_results["issues"].append("No services registered for monitoring")
                validation_results["recommendations"].append("Register core services (database, redis) for monitoring")
                validation_results["overall_valid"] = False
            
            validation_results["components"]["health_monitor"] = {
                "valid": len(service_health_monitor.services) > 0,
                "services_count": len(service_health_monitor.services)
            }
            
        except Exception as e:
            validation_results["issues"].append(f"Health monitor validation failed: {str(e)}")
            validation_results["overall_valid"] = False
        
        # Validate recovery system
        try:
            from app.services.service_recovery import service_recovery_manager
            
            recovery_strategies_count = sum(len(strategies) for strategies in service_recovery_manager.recovery_strategies.values())
            
            validation_results["components"]["recovery_manager"] = {
                "valid": recovery_strategies_count > 0,
                "strategies_count": recovery_strategies_count
            }
            
            if recovery_strategies_count == 0:
                validation_results["issues"].append("No recovery strategies configured")
                validation_results["recommendations"].append("Configure recovery strategies for critical services")
            
        except Exception as e:
            validation_results["issues"].append(f"Recovery system validation failed: {str(e)}")
            validation_results["overall_valid"] = False
        
        # Validate alerting system
        try:
            from app.services.alerting_service import alerting_service
            
            validation_results["components"]["alerting_service"] = {
                "valid": len(alerting_service.channels) > 0,
                "channels_count": len(alerting_service.channels),
                "rules_count": len(alerting_service.rules)
            }
            
            if len(alerting_service.channels) == 0:
                validation_results["recommendations"].append("Configure notification channels for alerts")
            
        except Exception as e:
            validation_results["issues"].append(f"Alerting system validation failed: {str(e)}")
            validation_results["overall_valid"] = False
        
        return validation_results
        
    except Exception as e:
        logger.error("Health system validation failed", error=str(e))
        return {
            "overall_valid": False,
            "error": str(e),
            "components": {},
            "issues": [f"Validation system error: {str(e)}"],
            "recommendations": ["Check health system initialization"]
        }