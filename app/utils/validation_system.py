"""
Comprehensive Validation System for AI Secretary application.
Coordinates configuration validation, environment checking, and service health monitoring.
Addresses Requirements 6.1, 6.2, 6.3, and 6.4 for complete deployment preparation validation.
"""

import logging
import os
import sys
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from .config_validator import ConfigValidator, ValidationReport, ValidationSeverity
from .environment_checker import EnvironmentChecker, EnvironmentReport

logger = logging.getLogger(__name__)


class ValidationLevel(Enum):
    """Validation levels for different deployment stages."""
    BASIC = "basic"          # Minimal checks for development
    STANDARD = "standard"    # Standard checks for staging
    COMPREHENSIVE = "comprehensive"  # Full checks for production


class DeploymentStage(Enum):
    """Deployment stages."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


@dataclass
class SystemValidationReport:
    """Comprehensive system validation report."""
    valid: bool = True
    stage: DeploymentStage = DeploymentStage.DEVELOPMENT
    level: ValidationLevel = ValidationLevel.BASIC
    
    # Individual reports
    config_report: Optional[ValidationReport] = None
    environment_report: Optional[EnvironmentReport] = None
    health_report: Optional[Any] = None  # HealthCheckResult - imported dynamically
    
    # Summary statistics
    total_checks: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    warnings: int = 0
    
    # Recommendations and actions
    critical_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    required_actions: List[str] = field(default_factory=list)
    
    # Service status
    services_healthy: int = 0
    services_total: int = 0
    fallback_services: List[str] = field(default_factory=list)
    
    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    duration: float = 0.0
    
    def add_critical_issue(self, issue: str, action: Optional[str] = None):
        """Add a critical issue that prevents deployment."""
        self.critical_issues.append(issue)
        self.valid = False
        if action:
            self.required_actions.append(action)
    
    def add_recommendation(self, recommendation: str):
        """Add a recommendation for improvement."""
        self.recommendations.append(recommendation)
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary."""
        return {
            'valid': self.valid,
            'stage': self.stage.value,
            'level': self.level.value,
            'total_checks': self.total_checks,
            'passed_checks': self.passed_checks,
            'failed_checks': self.failed_checks,
            'warnings': self.warnings,
            'critical_issues_count': len(self.critical_issues),
            'services_healthy': self.services_healthy,
            'services_total': self.services_total,
            'fallback_services_count': len(self.fallback_services),
            'duration': self.duration,
            'timestamp': self.timestamp.isoformat()
        }


class ValidationSystem:
    """
    Comprehensive validation system coordinator.
    
    Orchestrates configuration validation, environment checking, and service health monitoring
    to provide complete deployment readiness assessment.
    """
    
    def __init__(self, app=None, db=None):
        self.app = app
        self.db = db
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        
        # Initialize validators
        self.config_validator = None
        self.environment_checker = None
        self.health_validator = None
        
        if app:
            self.init_app(app, db)
    
    def init_app(self, app, db=None):
        """Initialize validation system with Flask app."""
        self.app = app
        self.db = db
        
        # Initialize validators
        self.config_validator = ConfigValidator()
        self.environment_checker = EnvironmentChecker()
        
        if db:
            # Import here to avoid circular imports
            from .health_validator import HealthValidator
            self.health_validator = HealthValidator(app, db)
    
    def validate_system(self, level: ValidationLevel = ValidationLevel.STANDARD,
                       stage: DeploymentStage = None) -> SystemValidationReport:
        """
        Run comprehensive system validation.
        
        Args:
            level: Validation level (basic, standard, comprehensive)
            stage: Deployment stage (development, staging, production)
            
        Returns:
            SystemValidationReport with complete validation results
        """
        start_time = datetime.now()
        
        # Determine stage if not provided
        if stage is None:
            flask_env = os.getenv('FLASK_ENV', 'development').lower()
            if flask_env == 'production':
                stage = DeploymentStage.PRODUCTION
            elif flask_env == 'staging':
                stage = DeploymentStage.STAGING
            else:
                stage = DeploymentStage.DEVELOPMENT
        
        report = SystemValidationReport(stage=stage, level=level)
        
        self.logger.info(f"Starting {level.value} validation for {stage.value} deployment")
        
        try:
            # 1. Configuration validation (always required)
            if self.config_validator:
                self.logger.info("Running configuration validation...")
                report.config_report = self.config_validator.validate_all()
                self._process_config_results(report)
            else:
                report.add_critical_issue("Configuration validator not initialized")
            
            # 2. Environment validation (standard and comprehensive)
            if level in [ValidationLevel.STANDARD, ValidationLevel.COMPREHENSIVE]:
                if self.environment_checker:
                    self.logger.info("Running environment validation...")
                    report.environment_report = self.environment_checker.validate_environment()
                    self._process_environment_results(report)
                else:
                    report.add_critical_issue("Environment checker not initialized")
            
            # 3. Health validation (comprehensive only, or if database available)
            if level == ValidationLevel.COMPREHENSIVE or (self.health_validator and self.db):
                if self.health_validator:
                    self.logger.info("Running health validation...")
                    report.health_report = self.health_validator.run_comprehensive_health_check()
                    self._process_health_results(report)
                else:
                    self.logger.warning("Health validator not available - skipping health checks")
            
            # 4. Stage-specific validations
            self._validate_stage_requirements(report, stage)
            
            # 5. Generate final recommendations
            self._generate_final_recommendations(report, stage, level)
            
        except Exception as e:
            report.add_critical_issue(f"Validation system failed: {str(e)}")
            self.logger.error(f"Validation system failed: {e}", exc_info=True)
        
        finally:
            report.duration = (datetime.now() - start_time).total_seconds()
            
            # Log final results
            if report.valid:
                self.logger.info(f"✅ System validation passed: {report.passed_checks}/{report.total_checks} checks")
            else:
                self.logger.error(f"❌ System validation failed: {len(report.critical_issues)} critical issues")
        
        return report
    
    def _process_config_results(self, report: SystemValidationReport):
        """Process configuration validation results."""
        config_report = report.config_report
        
        if not config_report:
            return
        
        # Count issues
        critical_count = len(config_report.critical_issues)
        error_count = len(config_report.errors)
        warning_count = len(config_report.warnings)
        
        report.total_checks += critical_count + error_count + warning_count + len(config_report.info)
        report.warnings += warning_count
        
        if critical_count > 0:
            report.failed_checks += critical_count
            for issue in config_report.critical_issues:
                report.add_critical_issue(f"Config: {issue.message}", issue.suggestion)
        
        if error_count > 0:
            report.failed_checks += error_count
            for issue in config_report.errors:
                report.add_critical_issue(f"Config: {issue.message}", issue.suggestion)
        
        if warning_count > 0:
            for issue in config_report.warnings:
                if issue.suggestion:
                    report.add_recommendation(f"Config: {issue.suggestion}")
        
        # Count services
        report.services_total += len(config_report.services)
        for service_name, service in config_report.services.items():
            if service.status.value == 'healthy':
                report.services_healthy += 1
            elif service.fallback_available:
                report.fallback_services.append(service_name)
        
        report.passed_checks += report.total_checks - report.failed_checks
    
    def _process_environment_results(self, report: SystemValidationReport):
        """Process environment validation results."""
        env_report = report.environment_report
        
        if not env_report:
            return
        
        # Count requirements
        met_count = len(env_report.requirements_met)
        failed_count = len(env_report.requirements_failed)
        
        report.total_checks += met_count + failed_count
        report.passed_checks += met_count
        report.failed_checks += failed_count
        report.warnings += len(env_report.warnings)
        
        # Process failed requirements
        for requirement in env_report.requirements_failed:
            report.add_critical_issue(f"Environment: {requirement} requirement not met")
        
        # Process errors
        for error in env_report.errors:
            report.add_critical_issue(f"Environment: {error.message}", error.suggestion)
        
        # Add recommendations
        for recommendation in env_report.recommendations:
            report.add_recommendation(f"Environment: {recommendation}")
    
    def _process_health_results(self, report: SystemValidationReport):
        """Process health validation results."""
        health_report = report.health_report
        
        if not health_report:
            return
        
        # Update counts
        report.total_checks += health_report.checks_total
        report.passed_checks += health_report.checks_passed
        report.failed_checks += health_report.checks_failed
        report.warnings += len(health_report.warnings)
        
        # Process issues
        for issue in health_report.issues:
            report.add_critical_issue(f"Health: {issue}")
        
        # Process external services
        if 'external_services' in health_report.details:
            services = health_report.details['external_services']
            for service_name, service_info in services.items():
                if service_info.get('fallback_available', False):
                    report.fallback_services.append(service_name)
    
    def _validate_stage_requirements(self, report: SystemValidationReport, stage: DeploymentStage):
        """Validate stage-specific requirements."""
        if stage == DeploymentStage.PRODUCTION:
            self._validate_production_requirements(report)
        elif stage == DeploymentStage.STAGING:
            self._validate_staging_requirements(report)
        else:
            self._validate_development_requirements(report)
    
    def _validate_production_requirements(self, report: SystemValidationReport):
        """Validate production-specific requirements."""
        # Check for production-critical settings
        if report.config_report:
            env_vars = report.config_report.environment
            
            # Debug mode check
            if env_vars.get('debug_mode', False):
                report.add_critical_issue(
                    "Debug mode enabled in production",
                    "Set FLASK_DEBUG=false for production"
                )
            
            # HTTPS enforcement
            if not env_vars.get('force_https', False):
                report.add_recommendation("Enable HTTPS enforcement for production security")
            
            # Secret key strength
            secret_key = os.getenv('SECRET_KEY', '')
            if len(secret_key) < 32:
                report.add_critical_issue(
                    "Weak secret key in production",
                    "Use a strong 32+ character SECRET_KEY"
                )
        
        # Database requirements
        database_url = os.getenv('DATABASE_URL', '')
        if 'sqlite' in database_url.lower():
            report.add_recommendation("Consider using PostgreSQL for production instead of SQLite")
    
    def _validate_staging_requirements(self, report: SystemValidationReport):
        """Validate staging-specific requirements."""
        # Staging should be similar to production but with some relaxed requirements
        if report.config_report:
            env_vars = report.config_report.environment
            
            if env_vars.get('debug_mode', False):
                report.add_recommendation("Consider disabling debug mode in staging")
    
    def _validate_development_requirements(self, report: SystemValidationReport):
        """Validate development-specific requirements."""
        # Development has minimal requirements
        if report.config_report and not report.config_report.valid:
            report.add_recommendation("Fix configuration issues for smoother development")
    
    def _generate_final_recommendations(self, report: SystemValidationReport, 
                                      stage: DeploymentStage, level: ValidationLevel):
        """Generate final recommendations based on validation results."""
        # Service fallback recommendations
        if report.fallback_services:
            report.add_recommendation(
                f"Configure services for full functionality: {', '.join(report.fallback_services)}"
            )
        
        # Stage-specific recommendations
        if stage == DeploymentStage.PRODUCTION and report.warnings > 0:
            report.add_recommendation("Address all warnings before production deployment")
        
        # Level-specific recommendations
        if level == ValidationLevel.BASIC and stage != DeploymentStage.DEVELOPMENT:
            report.add_recommendation("Run comprehensive validation for non-development deployments")
    
    def validate_for_deployment(self, target_stage: DeploymentStage) -> SystemValidationReport:
        """
        Validate system readiness for specific deployment stage.
        
        Args:
            target_stage: Target deployment stage
            
        Returns:
            SystemValidationReport with deployment readiness assessment
        """
        # Choose appropriate validation level based on stage
        if target_stage == DeploymentStage.PRODUCTION:
            level = ValidationLevel.COMPREHENSIVE
        elif target_stage == DeploymentStage.STAGING:
            level = ValidationLevel.STANDARD
        else:
            level = ValidationLevel.BASIC
        
        return self.validate_system(level=level, stage=target_stage)
    
    def get_quick_status(self) -> Dict[str, Any]:
        """
        Get quick system status without full validation.
        
        Returns:
            Dictionary with basic system status
        """
        status = {
            'timestamp': datetime.now().isoformat(),
            'config_file_exists': os.path.exists('.env'),
            'database_configured': bool(os.getenv('DATABASE_URL')),
            'python_version': f"{os.sys.version_info.major}.{os.sys.version_info.minor}.{os.sys.version_info.micro}",
            'flask_env': os.getenv('FLASK_ENV', 'development'),
            'debug_mode': os.getenv('FLASK_DEBUG', 'false').lower() in ['true', '1', 'yes']
        }
        
        # Quick service check
        services = ['OPENAI_API_KEY', 'REDIS_URL', 'GOOGLE_CLIENT_ID', 'STRIPE_SECRET_KEY']
        configured_services = []
        
        for service in services:
            value = os.getenv(service, '').strip()
            if value and not value.startswith('your-'):
                configured_services.append(service.lower().replace('_', ' '))
        
        status['configured_services'] = configured_services
        status['services_count'] = len(configured_services)
        
        return status


# Convenience functions
def validate_system(app, db=None, level: ValidationLevel = ValidationLevel.STANDARD):
    """Convenience function to validate system."""
    validator = ValidationSystem(app, db)
    return validator.validate_system(level=level)


def validate_for_production(app, db=None):
    """Convenience function to validate for production deployment."""
    validator = ValidationSystem(app, db)
    return validator.validate_for_deployment(DeploymentStage.PRODUCTION)


def get_system_status() -> Dict[str, Any]:
    """Convenience function to get quick system status."""
    validator = ValidationSystem()
    return validator.get_quick_status()


if __name__ == "__main__":
    # CLI usage
    import json
    import sys
    
    # Quick status check
    status = get_system_status()
    print(json.dumps(status, indent=2))
    
    # If Flask app is available, run full validation
    try:
        # Import Flask here to avoid issues
        import flask
        app = flask.Flask(__name__)
        
        # Load config from environment
        if hasattr(app.config, 'from_prefixed_env'):
            app.config.from_prefixed_env()
        
        result = validate_system(app, level=ValidationLevel.COMPREHENSIVE)
        
        print("\n" + "="*50)
        print("COMPREHENSIVE VALIDATION RESULTS")
        print("="*50)
        print(json.dumps(result.get_summary(), indent=2))
        
        if not result.valid:
            print("\nCRITICAL ISSUES:")
            for issue in result.critical_issues:
                print(f"  ❌ {issue}")
            
            print("\nREQUIRED ACTIONS:")
            for action in result.required_actions:
                print(f"  🔧 {action}")
        
        if result.recommendations:
            print("\nRECOMMENDATIONS:")
            for rec in result.recommendations:
                print(f"  💡 {rec}")
        
        sys.exit(0 if result.valid else 1)
        
    except ImportError:
        print("Flask not available - running basic validation only")
        sys.exit(0)