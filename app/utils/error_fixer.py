"""Main error fixing utility that combines database, context, and route fixes."""
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from flask import Flask, current_app

from app.utils.database_fixer import DatabaseFixer, DatabaseFixResult
from app.utils.context_fixer import ContextFixer, ContextFixResult
from app.utils.route_validator import RouteValidator, RouteValidationResult


logger = logging.getLogger(__name__)


@dataclass
class ErrorFixResult:
    """Combined result of all error fixes."""
    success: bool
    database_fixes: DatabaseFixResult
    context_fixes: ContextFixResult
    route_validation: RouteValidationResult
    summary: Dict[str, Any]


class ErrorFixer:
    """Main error fixer that coordinates database, context, and route fixes."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app or current_app
        self.database_fixer = DatabaseFixer(self.app)
        self.context_fixer = ContextFixer(self.app)
        self.route_validator = RouteValidator(self.app)
    
    def fix_all_errors(self) -> ErrorFixResult:
        """Fix all application errors."""
        logger.info("🚀 Starting comprehensive error fixing...")
        
        try:
            # Fix database issues first
            logger.info("🔧 Fixing database issues...")
            database_result = self.database_fixer.fix_all_database_issues()
            
            # Fix context issues
            logger.info("🔧 Fixing context issues...")
            context_result = self.context_fixer.fix_all_context_issues()
            
            # Validate and fix routes
            logger.info("🔧 Validating routes...")
            route_result = self.route_validator.validate_all_routes()
            
            # Try to fix common route issues
            self.route_validator.fix_common_route_issues()
            
            # Generate summary
            summary = self._generate_summary(database_result, context_result, route_result)
            
            result = ErrorFixResult(
                success=database_result.success and context_result.success and route_result.success,
                database_fixes=database_result,
                context_fixes=context_result,
                route_validation=route_result,
                summary=summary
            )
            
            logger.info("✅ Comprehensive error fixing completed")
            self._log_summary(result)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to fix errors: {e}")
            # Return a failed result
            return ErrorFixResult(
                success=False,
                database_fixes=DatabaseFixResult(False, [], [], [str(e)], []),
                context_fixes=ContextFixResult(False, [], [], [str(e)], []),
                route_validation=RouteValidationResult(False, 0, 0, [], [], [], [str(e)]),
                summary={'error': str(e)}
            )
    
    def _generate_summary(self, db_result: DatabaseFixResult, ctx_result: ContextFixResult, 
                         route_result: RouteValidationResult) -> Dict[str, Any]:
        """Generate a summary of all fixes."""
        return {
            'total_fixes': (
                len(db_result.fixed_issues) + 
                len(ctx_result.fixed_issues) + 
                len(route_result.fixed_issues)
            ),
            'total_errors': (
                len(db_result.errors) + 
                len(ctx_result.errors) + 
                len(route_result.errors)
            ),
            'total_warnings': (
                len(db_result.warnings) + 
                len(ctx_result.warnings) + 
                len(route_result.warnings)
            ),
            'database': {
                'fixes': len(db_result.fixed_issues),
                'errors': len(db_result.errors),
                'warnings': len(db_result.warnings)
            },
            'context': {
                'fixes': len(ctx_result.fixed_issues),
                'errors': len(ctx_result.errors),
                'warnings': len(ctx_result.warnings)
            },
            'routes': {
                'total': route_result.total_routes,
                'valid': route_result.valid_routes,
                'issues': len(route_result.issues),
                'fixes': len(route_result.fixed_issues)
            }
        }
    
    def _log_summary(self, result: ErrorFixResult):
        """Log a summary of the fixes."""
        summary = result.summary
        
        logger.info("📊 Error Fixing Summary:")
        logger.info(f"   Total Fixes Applied: {summary['total_fixes']}")
        logger.info(f"   Total Errors: {summary['total_errors']}")
        logger.info(f"   Total Warnings: {summary['total_warnings']}")
        
        logger.info("🗄️  Database Fixes:")
        logger.info(f"   Fixes: {summary['database']['fixes']}")
        logger.info(f"   Errors: {summary['database']['errors']}")
        logger.info(f"   Warnings: {summary['database']['warnings']}")
        
        logger.info("🔄 Context Fixes:")
        logger.info(f"   Fixes: {summary['context']['fixes']}")
        logger.info(f"   Errors: {summary['context']['errors']}")
        logger.info(f"   Warnings: {summary['context']['warnings']}")
        
        logger.info("🛣️  Route Validation:")
        logger.info(f"   Total Routes: {summary['routes']['total']}")
        logger.info(f"   Valid Routes: {summary['routes']['valid']}")
        logger.info(f"   Issues Found: {summary['routes']['issues']}")
        logger.info(f"   Fixes Applied: {summary['routes']['fixes']}")
    
    def generate_detailed_report(self) -> str:
        """Generate a detailed report of all fixes."""
        result = self.fix_all_errors()
        
        report = []
        report.append("# Application Error Fixing Report")
        report.append(f"Overall Success: {'✅ Yes' if result.success else '❌ No'}")
        report.append("")
        
        # Summary
        report.append("## Summary")
        summary = result.summary
        report.append(f"- Total Fixes Applied: {summary['total_fixes']}")
        report.append(f"- Total Errors: {summary['total_errors']}")
        report.append(f"- Total Warnings: {summary['total_warnings']}")
        report.append("")
        
        # Database fixes
        report.append("## Database Fixes")
        db_result = result.database_fixes
        report.append(f"Success: {'✅ Yes' if db_result.success else '❌ No'}")
        
        if db_result.fixed_issues:
            report.append("### Fixed Issues:")
            for issue in db_result.fixed_issues:
                report.append(f"- ✅ {issue}")
        
        if db_result.errors:
            report.append("### Errors:")
            for error in db_result.errors:
                report.append(f"- ❌ {error}")
        
        if db_result.warnings:
            report.append("### Warnings:")
            for warning in db_result.warnings:
                report.append(f"- ⚠️ {warning}")
        
        report.append("")
        
        # Context fixes
        report.append("## Context Fixes")
        ctx_result = result.context_fixes
        report.append(f"Success: {'✅ Yes' if ctx_result.success else '❌ No'}")
        
        if ctx_result.fixed_issues:
            report.append("### Fixed Issues:")
            for issue in ctx_result.fixed_issues:
                report.append(f"- ✅ {issue}")
        
        if ctx_result.errors:
            report.append("### Errors:")
            for error in ctx_result.errors:
                report.append(f"- ❌ {error}")
        
        if ctx_result.warnings:
            report.append("### Warnings:")
            for warning in ctx_result.warnings:
                report.append(f"- ⚠️ {warning}")
        
        report.append("")
        
        # Route validation
        report.append("## Route Validation")
        route_result = result.route_validation
        report.append(f"Success: {'✅ Yes' if route_result.success else '❌ No'}")
        report.append(f"Total Routes: {route_result.total_routes}")
        report.append(f"Valid Routes: {route_result.valid_routes}")
        
        if route_result.issues:
            report.append("### Route Issues:")
            for issue in route_result.issues:
                severity_emoji = {
                    'critical': '🔴',
                    'high': '🟠', 
                    'medium': '🟡',
                    'low': '🟢'
                }.get(issue.severity, '⚪')
                report.append(f"- {severity_emoji} **{issue.route}** ({issue.method}): {issue.description}")
        
        if route_result.fixed_issues:
            report.append("### Fixed Issues:")
            for issue in route_result.fixed_issues:
                report.append(f"- ✅ {issue}")
        
        if route_result.errors:
            report.append("### Errors:")
            for error in route_result.errors:
                report.append(f"- ❌ {error}")
        
        return '\n'.join(report)
    
    def quick_health_check(self) -> Dict[str, Any]:
        """Perform a quick health check of the application."""
        try:
            health_status = {
                'database': 'unknown',
                'context': 'unknown',
                'routes': 'unknown',
                'overall': 'unknown'
            }
            
            # Quick database check
            try:
                if self.database_fixer.check_table_exists('users'):
                    health_status['database'] = 'healthy'
                else:
                    health_status['database'] = 'issues'
            except Exception:
                health_status['database'] = 'error'
            
            # Quick context check
            try:
                with self.app.app_context():
                    # Try a simple operation that requires context
                    from flask import current_app
                    if current_app:
                        health_status['context'] = 'healthy'
                    else:
                        health_status['context'] = 'issues'
            except Exception:
                health_status['context'] = 'error'
            
            # Quick route check
            try:
                route_count = len(list(self.app.url_map.iter_rules()))
                if route_count > 0:
                    health_status['routes'] = 'healthy'
                else:
                    health_status['routes'] = 'issues'
            except Exception:
                health_status['routes'] = 'error'
            
            # Overall status
            if all(status == 'healthy' for status in [health_status['database'], health_status['context'], health_status['routes']]):
                health_status['overall'] = 'healthy'
            elif any(status == 'error' for status in [health_status['database'], health_status['context'], health_status['routes']]):
                health_status['overall'] = 'error'
            else:
                health_status['overall'] = 'issues'
            
            return health_status
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                'database': 'error',
                'context': 'error', 
                'routes': 'error',
                'overall': 'error',
                'error': str(e)
            }