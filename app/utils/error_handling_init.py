"""
Error Handling Initialization

This module initializes all error handling systems and integrates them
with the Flask application.
"""
import logging
from typing import Dict, Any, Optional
from flask import Flask
import structlog

logger = structlog.get_logger(__name__)


def init_comprehensive_error_handling(app: Flask) -> Dict[str, Any]:
    """
    Initialize comprehensive error handling system.
    
    This function integrates all error handling components:
    - Enhanced logging with structured logging
    - Graceful degradation for service failures
    - User-friendly notifications
    - Multilingual error messages
    - Error tracking and analytics
    
    Args:
        app: Flask application instance
        
    Returns:
        Dictionary with initialized error handling components
    """
    logger.info("🛡️ Initializing comprehensive error handling system")
    
    error_handlers = {}
    initialization_errors = []
    
    try:
        # 1. Initialize Enhanced Logging Manager
        logger.info("📝 Initializing enhanced logging manager")
        try:
            from app.utils.enhanced_logging import init_enhanced_logging
            enhanced_logging_manager = init_enhanced_logging(app)
            error_handlers['enhanced_logging'] = enhanced_logging_manager
            logger.info("✅ Enhanced logging manager initialized")
        except Exception as e:
            initialization_errors.append(f"Enhanced logging initialization failed: {e}")
            logger.error(f"❌ Enhanced logging initialization failed: {e}")
    
        # 2. Initialize Graceful Degradation Manager
        logger.info("🛡️ Initializing graceful degradation manager")
        try:
            from app.utils.graceful_degradation import init_graceful_degradation
            graceful_degradation_manager = init_graceful_degradation(app)
            error_handlers['graceful_degradation'] = graceful_degradation_manager
            logger.info("✅ Graceful degradation manager initialized")
        except Exception as e:
            initialization_errors.append(f"Graceful degradation initialization failed: {e}")
            logger.error(f"❌ Graceful degradation initialization failed: {e}")
    
        # 3. Initialize User Notification Manager
        logger.info("📢 Initializing user notification manager")
        try:
            from app.utils.user_notifications import init_user_notifications
            user_notification_manager = init_user_notifications(app)
            error_handlers['user_notifications'] = user_notification_manager
            logger.info("✅ User notification manager initialized")
        except Exception as e:
            initialization_errors.append(f"User notification initialization failed: {e}")
            logger.error(f"❌ User notification initialization failed: {e}")
    
        # 4. Initialize Error Formatter
        logger.info("🎨 Initializing error formatter")
        try:
            from app.utils.error_formatter import get_error_formatter
            error_formatter = get_error_formatter()
            error_handlers['error_formatter'] = error_formatter
            logger.info("✅ Error formatter initialized")
        except Exception as e:
            initialization_errors.append(f"Error formatter initialization failed: {e}")
            logger.error(f"❌ Error formatter initialization failed: {e}")
    
        # 5. Initialize Comprehensive Error Handler
        logger.info("🔧 Initializing comprehensive error handler")
        try:
            from app.utils.comprehensive_error_handler import init_comprehensive_error_handler
            comprehensive_error_handler = init_comprehensive_error_handler(app)
            error_handlers['comprehensive_handler'] = comprehensive_error_handler
            logger.info("✅ Comprehensive error handler initialized")
        except Exception as e:
            initialization_errors.append(f"Comprehensive error handler initialization failed: {e}")
            logger.error(f"❌ Comprehensive error handler initialization failed: {e}")
    
        # 6. Register Flask Error Handlers
        logger.info("🔗 Registering Flask error handlers")
        try:
            from app.utils.errors import register_error_handlers
            register_error_handlers(app)
            logger.info("✅ Flask error handlers registered")
        except Exception as e:
            initialization_errors.append(f"Flask error handlers registration failed: {e}")
            logger.error(f"❌ Flask error handlers registration failed: {e}")
    
        # 7. Initialize Multilingual Error Support
        logger.info("🌐 Initializing multilingual error support")
        try:
            _init_multilingual_error_support(app, error_handlers)
            logger.info("✅ Multilingual error support initialized")
        except Exception as e:
            initialization_errors.append(f"Multilingual error support initialization failed: {e}")
            logger.error(f"❌ Multilingual error support initialization failed: {e}")
    
        # 8. Setup Error Notification System
        logger.info("🔔 Setting up error notification system")
        try:
            _setup_error_notification_system(app, error_handlers)
            logger.info("✅ Error notification system setup complete")
        except Exception as e:
            initialization_errors.append(f"Error notification system setup failed: {e}")
            logger.error(f"❌ Error notification system setup failed: {e}")
    
        # 9. Configure Service Health Monitoring Integration
        logger.info("🏥 Configuring service health monitoring integration")
        try:
            _configure_health_monitoring_integration(app, error_handlers)
            logger.info("✅ Service health monitoring integration configured")
        except Exception as e:
            initialization_errors.append(f"Health monitoring integration failed: {e}")
            logger.error(f"❌ Health monitoring integration failed: {e}")
    
        # 10. Initialize Service Error Handlers
        logger.info("🔧 Initializing service error handlers")
        try:
            from app.utils.service_error_handlers import init_service_error_handlers
            service_error_handlers = init_service_error_handlers(app)
            error_handlers['service_error_handlers'] = service_error_handlers
            logger.info("✅ Service error handlers initialized")
        except Exception as e:
            initialization_errors.append(f"Service error handlers initialization failed: {e}")
            logger.error(f"❌ Service error handlers initialization failed: {e}")

        # 11. Initialize Multilingual Error Support
        logger.info("🌐 Initializing multilingual error messages")
        try:
            from app.utils.multilingual_errors import get_multilingual_error_messages
            multilingual_messages = get_multilingual_error_messages()
            error_handlers['multilingual_messages'] = multilingual_messages
            logger.info("✅ Multilingual error messages initialized")
        except Exception as e:
            initialization_errors.append(f"Multilingual error messages initialization failed: {e}")
            logger.error(f"❌ Multilingual error messages initialization failed: {e}")

        # 12. Initialize Error Notification System
        logger.info("🔔 Initializing error notification system")
        try:
            from app.utils.error_notification_system import init_error_notification_system
            error_notification_system = init_error_notification_system(app)
            error_handlers['error_notification_system'] = error_notification_system
            logger.info("✅ Error notification system initialized")
        except Exception as e:
            initialization_errors.append(f"Error notification system initialization failed: {e}")
            logger.error(f"❌ Error notification system initialization failed: {e}")

        # 13. Setup Error Analytics and Reporting
        logger.info("📊 Setting up error analytics and reporting")
        try:
            _setup_error_analytics(app, error_handlers)
            logger.info("✅ Error analytics and reporting setup complete")
        except Exception as e:
            initialization_errors.append(f"Error analytics setup failed: {e}")
            logger.error(f"❌ Error analytics setup failed: {e}")
    
        # Store error handlers in app config for access
        app.config['ERROR_HANDLERS'] = error_handlers
        app.config['ERROR_HANDLING_INITIALIZATION_ERRORS'] = initialization_errors
    
        # Log initialization summary
        successful_components = len(error_handlers)
        failed_components = len(initialization_errors)
        
        if failed_components == 0:
            logger.info(f"🎉 Comprehensive error handling system initialized successfully")
            logger.info(f"   ✅ {successful_components} components initialized")
        else:
            logger.warning(f"⚠️ Comprehensive error handling system initialized with issues")
            logger.warning(f"   ✅ {successful_components} components initialized")
            logger.warning(f"   ❌ {failed_components} components failed")
            
            for error in initialization_errors:
                logger.warning(f"   - {error}")
    
        return {
            'error_handlers': error_handlers,
            'initialization_errors': initialization_errors,
            'successful_components': successful_components,
            'failed_components': failed_components
        }
        
    except Exception as e:
        logger.critical(f"🚨 Critical error during error handling system initialization: {e}")
        app.config['ERROR_HANDLING_CRITICAL_FAILURE'] = str(e)
        raise


def _init_multilingual_error_support(app: Flask, error_handlers: Dict[str, Any]):
    """Initialize multilingual error message support."""
    try:
        # Check if Babel is available and configured
        if 'babel' in app.extensions:
            logger.info("🌐 Babel detected - enabling multilingual error messages")
            
            # Configure error formatter for multilingual support
            if 'error_formatter' in error_handlers:
                error_formatter = error_handlers['error_formatter']
                
                # Add multilingual error message templates
                multilingual_templates = _get_multilingual_error_templates()
                if hasattr(error_formatter, 'user_friendly_messages'):
                    error_formatter.user_friendly_messages.update(multilingual_templates)
            
            # Configure user notifications for multilingual support
            if 'user_notifications' in error_handlers:
                user_notification_manager = error_handlers['user_notifications']
                
                # Add multilingual notification templates
                multilingual_notification_templates = _get_multilingual_notification_templates()
                if hasattr(user_notification_manager, '_notification_templates'):
                    user_notification_manager._notification_templates.update(multilingual_notification_templates)
            
            app.config['MULTILINGUAL_ERROR_SUPPORT'] = True
            logger.info("✅ Multilingual error support configured")
            
        else:
            logger.info("ℹ️ Babel not available - using English-only error messages")
            app.config['MULTILINGUAL_ERROR_SUPPORT'] = False
            
    except Exception as e:
        logger.error(f"Failed to initialize multilingual error support: {e}")
        app.config['MULTILINGUAL_ERROR_SUPPORT'] = False


def _setup_error_notification_system(app: Flask, error_handlers: Dict[str, Any]):
    """Setup integrated error notification system."""
    try:
        # Get notification manager
        notification_manager = error_handlers.get('user_notifications')
        if not notification_manager:
            logger.warning("User notification manager not available - skipping notification setup")
            return
        
        # Configure automatic error notifications
        app.config['AUTO_ERROR_NOTIFICATIONS'] = app.config.get('AUTO_ERROR_NOTIFICATIONS', True)
        app.config['ERROR_NOTIFICATION_THRESHOLD'] = app.config.get('ERROR_NOTIFICATION_THRESHOLD', 'medium')
        
        # Setup error notification templates for different error types
        error_notification_templates = {
            'database_error_critical': {
                'type': notification_manager.NotificationType.ERROR,
                'priority': notification_manager.NotificationPriority.URGENT,
                'title': 'Critical Database Error',
                'message': 'A critical database error has occurred. Some features may be unavailable.',
                'dismissible': False,
                'auto_dismiss': False,
                'resolution_steps': [
                    'Check database connection',
                    'Review database logs',
                    'Contact system administrator',
                    'Monitor system status'
                ]
            },
            'service_degradation_warning': {
                'type': notification_manager.NotificationType.WARNING,
                'priority': notification_manager.NotificationPriority.MEDIUM,
                'title': 'Service Performance Issue',
                'message': 'Some services are experiencing performance issues.',
                'dismissible': True,
                'auto_dismiss': False,
                'resolution_steps': [
                    'Try refreshing the page',
                    'Wait a few moments and try again',
                    'Contact support if issues persist'
                ]
            },
            'configuration_error_high': {
                'type': notification_manager.NotificationType.ERROR,
                'priority': notification_manager.NotificationPriority.HIGH,
                'title': 'Configuration Issue',
                'message': 'A configuration issue is affecting system functionality.',
                'dismissible': False,
                'auto_dismiss': False,
                'resolution_steps': [
                    'Review system configuration',
                    'Check environment variables',
                    'Restart application if necessary',
                    'Contact administrator for assistance'
                ]
            }
        }
        
        # Add templates to notification manager
        if hasattr(notification_manager, '_notification_templates'):
            notification_manager._notification_templates.update(error_notification_templates)
        
        logger.info("✅ Error notification system configured")
        
    except Exception as e:
        logger.error(f"Failed to setup error notification system: {e}")


def _configure_health_monitoring_integration(app: Flask, error_handlers: Dict[str, Any]):
    """Configure integration with service health monitoring."""
    try:
        # Get graceful degradation manager
        degradation_manager = error_handlers.get('graceful_degradation')
        notification_manager = error_handlers.get('user_notifications')
        
        if not degradation_manager or not notification_manager:
            logger.warning("Required managers not available - skipping health monitoring integration")
            return
        
        # Setup health status change callbacks
        def on_service_degradation(service_name: str, level: str, reason: str):
            """Handle service degradation events."""
            try:
                # Create user notification
                notification_manager.notify_service_degradation(service_name, level, reason)
                
                # Log the degradation
                if 'enhanced_logging' in error_handlers:
                    enhanced_logging = error_handlers['enhanced_logging']
                    enhanced_logging.log_service_issue('service_degradation',
                                                     service_name=service_name,
                                                     degradation_level=level,
                                                     reason=reason)
                
                logger.info(f"Service degradation handled: {service_name} -> {level}")
                
            except Exception as e:
                logger.error(f"Failed to handle service degradation: {e}")
        
        def on_service_recovery(service_name: str):
            """Handle service recovery events."""
            try:
                # Create recovery notification
                notification_manager.notify_service_recovery(service_name)
                
                # Log the recovery
                if 'enhanced_logging' in error_handlers:
                    enhanced_logging = error_handlers['enhanced_logging']
                    enhanced_logging.log_service_issue('service_recovery',
                                                     service_name=service_name)
                
                logger.info(f"Service recovery handled: {service_name}")
                
            except Exception as e:
                logger.error(f"Failed to handle service recovery: {e}")
        
        # Store callbacks in app config for use by health monitoring
        app.config['SERVICE_DEGRADATION_CALLBACK'] = on_service_degradation
        app.config['SERVICE_RECOVERY_CALLBACK'] = on_service_recovery
        
        logger.info("✅ Health monitoring integration configured")
        
    except Exception as e:
        logger.error(f"Failed to configure health monitoring integration: {e}")


def _setup_error_analytics(app: Flask, error_handlers: Dict[str, Any]):
    """Setup error analytics and reporting."""
    try:
        # Configure error analytics
        app.config['ERROR_ANALYTICS_ENABLED'] = app.config.get('ERROR_ANALYTICS_ENABLED', True)
        app.config['ERROR_REPORTING_ENABLED'] = app.config.get('ERROR_REPORTING_ENABLED', True)
        
        # Setup error statistics endpoint
        @app.route('/api/v1/admin/error-statistics')
        def get_error_statistics():
            """Get comprehensive error statistics."""
            try:
                from flask import jsonify
                from flask_jwt_extended import jwt_required, get_jwt_identity
                
                # This would normally require admin authentication
                # For now, we'll make it available for debugging
                
                stats = {}
                
                # Get stats from each error handler
                if 'enhanced_logging' in error_handlers:
                    stats['logging'] = error_handlers['enhanced_logging'].get_logging_stats()
                
                if 'graceful_degradation' in error_handlers:
                    stats['service_degradation'] = error_handlers['graceful_degradation'].get_service_status_summary()
                
                if 'user_notifications' in error_handlers:
                    stats['notifications'] = error_handlers['user_notifications'].get_notification_stats()
                
                if 'comprehensive_handler' in error_handlers:
                    stats['comprehensive'] = error_handlers['comprehensive_handler'].get_error_statistics()
                
                return jsonify({
                    'status': 'success',
                    'data': stats,
                    'timestamp': logger.info("Error statistics requested")
                })
                
            except Exception as e:
                logger.error(f"Failed to get error statistics: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to retrieve error statistics',
                    'error': str(e)
                }), 500
        
        # Setup error reporting endpoint
        @app.route('/api/v1/service/error-report', methods=['POST'])
        def submit_error_report():
            """Submit error report from client."""
            try:
                from flask import request, jsonify
                
                error_report = request.get_json()
                
                # Log the error report
                if 'enhanced_logging' in error_handlers:
                    enhanced_logging = error_handlers['enhanced_logging']
                    enhanced_logging.context_logger.log_with_context(
                        'error',
                        'Client error report received',
                        error_report=error_report
                    )
                
                logger.info("Client error report received and logged")
                
                return jsonify({
                    'status': 'success',
                    'message': 'Error report received and logged'
                })
                
            except Exception as e:
                logger.error(f"Failed to process error report: {e}")
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to process error report'
                }), 500
        
        logger.info("✅ Error analytics and reporting configured")
        
    except Exception as e:
        logger.error(f"Failed to setup error analytics: {e}")


def _get_multilingual_error_templates() -> Dict[str, Dict[str, Any]]:
    """Get multilingual error message templates."""
    # This would normally load from translation files
    # For now, we'll provide basic templates
    return {
        'system_unavailable_de': {
            'user': 'Das System ist vorübergehend nicht verfügbar. Bitte versuchen Sie es später erneut.',
            'admin': 'Systemausfall erkannt. Überprüfen Sie die Systemkomponenten.',
            'resolution_steps': [
                'Systemstatus überprüfen',
                'Dienste neu starten',
                'Systemadministrator kontaktieren'
            ]
        },
        'system_unavailable_uk': {
            'user': 'Система тимчасово недоступна. Будь ласка, спробуйте пізніше.',
            'admin': 'Виявлено збій системи. Перевірте системні компоненти.',
            'resolution_steps': [
                'Перевірити статус системи',
                'Перезапустити сервіси',
                'Звернутися до системного адміністратора'
            ]
        }
    }


def _get_multilingual_notification_templates() -> Dict[str, Dict[str, Any]]:
    """Get multilingual notification templates."""
    # This would normally load from translation files
    # For now, we'll provide basic templates
    return {
        'service_unavailable_de': {
            'type': 'error',
            'priority': 'high',
            'title': 'Dienst nicht verfügbar',
            'message': 'Ein wichtiger Dienst ist vorübergehend nicht verfügbar.',
            'dismissible': True,
            'auto_dismiss': False
        },
        'service_unavailable_uk': {
            'type': 'error',
            'priority': 'high',
            'title': 'Сервіс недоступний',
            'message': 'Важливий сервіс тимчасово недоступний.',
            'dismissible': True,
            'auto_dismiss': False
        }
    }


def get_error_handling_status(app: Flask) -> Dict[str, Any]:
    """Get current error handling system status."""
    try:
        error_handlers = app.config.get('ERROR_HANDLERS', {})
        initialization_errors = app.config.get('ERROR_HANDLING_INITIALIZATION_ERRORS', [])
        
        status = {
            'initialized': len(error_handlers) > 0,
            'components': {
                'enhanced_logging': 'enhanced_logging' in error_handlers,
                'graceful_degradation': 'graceful_degradation' in error_handlers,
                'user_notifications': 'user_notifications' in error_handlers,
                'error_formatter': 'error_formatter' in error_handlers,
                'comprehensive_handler': 'comprehensive_handler' in error_handlers
            },
            'multilingual_support': app.config.get('MULTILINGUAL_ERROR_SUPPORT', False),
            'auto_notifications': app.config.get('AUTO_ERROR_NOTIFICATIONS', False),
            'analytics_enabled': app.config.get('ERROR_ANALYTICS_ENABLED', False),
            'initialization_errors': initialization_errors,
            'critical_failure': app.config.get('ERROR_HANDLING_CRITICAL_FAILURE')
        }
        
        # Calculate health score
        total_components = len(status['components'])
        working_components = sum(1 for working in status['components'].values() if working)
        status['health_score'] = (working_components / total_components) * 100 if total_components > 0 else 0
        
        return status
        
    except Exception as e:
        logger.error(f"Failed to get error handling status: {e}")
        return {
            'initialized': False,
            'error': str(e),
            'health_score': 0
        }