"""Route validation and fixing utilities."""
import logging
import re
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass
from flask import Flask, current_app
from werkzeug.routing import Rule
from collections import defaultdict


logger = logging.getLogger(__name__)


@dataclass
class RouteIssue:
    """Represents a route issue."""
    route: str
    method: str
    issue_type: str
    description: str
    severity: str  # 'low', 'medium', 'high', 'critical'


@dataclass
class RouteValidationResult:
    """Result of route validation."""
    success: bool
    total_routes: int
    valid_routes: int
    issues: List[RouteIssue]
    fixed_issues: List[str]
    warnings: List[str]
    errors: List[str]


class RouteValidator:
    """Validates and fixes Flask route issues."""
    
    def __init__(self, app: Optional[Flask] = None):
        self.app = app or current_app
        self.issues = []
        self.fixed_issues = []
        self.warnings = []
        self.errors = []
    
    def validate_all_routes(self) -> RouteValidationResult:
        """Validate all routes in the application."""
        logger.info("🔍 Starting route validation...")
        
        # Reset tracking lists
        self.issues = []
        self.fixed_issues = []
        self.warnings = []
        self.errors = []
        
        try:
            with self.app.app_context():
                self._perform_route_validation()
                
        except Exception as e:
            logger.error(f"Failed to validate routes: {e}")
            self.errors.append(f"Failed to validate routes: {e}")
        
        result = RouteValidationResult(
            success=len(self.errors) == 0,
            total_routes=len(list(self.app.url_map.iter_rules())),
            valid_routes=len(list(self.app.url_map.iter_rules())) - len(self.issues),
            issues=self.issues,
            fixed_issues=self.fixed_issues,
            warnings=self.warnings,
            errors=self.errors
        )
        
        logger.info(f"✅ Route validation completed. Total: {result.total_routes}, Issues: {len(result.issues)}")
        return result
    
    def _perform_route_validation(self):
        """Perform all route validations."""
        # Check for duplicate routes
        self._check_duplicate_routes()
        
        # Check for conflicting routes
        self._check_conflicting_routes()
        
        # Check route accessibility
        self._check_route_accessibility()
        
        # Check route patterns
        self._check_route_patterns()
        
        # Check endpoint naming
        self._check_endpoint_naming()
        
        # Check for missing error handlers
        self._check_error_handlers()
    
    def _check_duplicate_routes(self):
        """Check for duplicate route definitions."""
        try:
            route_signatures = defaultdict(list)
            
            for rule in self.app.url_map.iter_rules():
                # Create signature from rule pattern and methods
                methods = sorted(rule.methods - {'HEAD', 'OPTIONS'})  # Exclude automatic methods
                signature = (rule.rule, tuple(methods))
                route_signatures[signature].append(rule)
            
            # Find duplicates
            for signature, rules in route_signatures.items():
                if len(rules) > 1:
                    route_pattern, methods = signature
                    endpoints = [rule.endpoint for rule in rules]
                    
                    issue = RouteIssue(
                        route=route_pattern,
                        method=', '.join(methods),
                        issue_type='duplicate_route',
                        description=f"Duplicate route definition with endpoints: {', '.join(endpoints)}",
                        severity='high'
                    )
                    self.issues.append(issue)
                    
        except Exception as e:
            logger.error(f"Failed to check duplicate routes: {e}")
            self.errors.append(f"Failed to check duplicate routes: {e}")
    
    def _check_conflicting_routes(self):
        """Check for conflicting route patterns."""
        try:
            rules = list(self.app.url_map.iter_rules())
            
            for i, rule1 in enumerate(rules):
                for rule2 in rules[i+1:]:
                    if self._routes_conflict(rule1, rule2):
                        issue = RouteIssue(
                            route=f"{rule1.rule} vs {rule2.rule}",
                            method=', '.join(rule1.methods & rule2.methods - {'HEAD', 'OPTIONS'}),
                            issue_type='conflicting_routes',
                            description=f"Routes may conflict: {rule1.endpoint} and {rule2.endpoint}",
                            severity='medium'
                        )
                        self.issues.append(issue)
                        
        except Exception as e:
            logger.error(f"Failed to check conflicting routes: {e}")
            self.errors.append(f"Failed to check conflicting routes: {e}")
    
    def _routes_conflict(self, rule1: Rule, rule2: Rule) -> bool:
        """Check if two routes might conflict."""
        # Check if methods overlap
        common_methods = rule1.methods & rule2.methods - {'HEAD', 'OPTIONS'}
        if not common_methods:
            return False
        
        # Simple pattern conflict detection
        pattern1 = self._normalize_route_pattern(rule1.rule)
        pattern2 = self._normalize_route_pattern(rule2.rule)
        
        # Check for potential conflicts with variable parts
        if self._patterns_might_conflict(pattern1, pattern2):
            return True
        
        return False
    
    def _normalize_route_pattern(self, pattern: str) -> str:
        """Normalize route pattern for comparison."""
        # Replace variable parts with placeholders
        normalized = re.sub(r'<[^>]+>', '<var>', pattern)
        return normalized
    
    def _patterns_might_conflict(self, pattern1: str, pattern2: str) -> bool:
        """Check if two normalized patterns might conflict."""
        # Split patterns into parts
        parts1 = [p for p in pattern1.split('/') if p]
        parts2 = [p for p in pattern2.split('/') if p]
        
        # Different lengths might still conflict if one is a prefix
        min_len = min(len(parts1), len(parts2))
        
        for i in range(min_len):
            p1, p2 = parts1[i], parts2[i]
            
            # If both are variables or one is variable, they might conflict
            if p1 == '<var>' or p2 == '<var>' or p1 == p2:
                continue
            else:
                # Different fixed parts, no conflict
                return False
        
        # If we got here, patterns might conflict
        return True
    
    def _check_route_accessibility(self):
        """Check if routes are accessible (have valid view functions)."""
        try:
            for rule in self.app.url_map.iter_rules():
                try:
                    view_func = self.app.view_functions.get(rule.endpoint)
                    if not view_func:
                        issue = RouteIssue(
                            route=rule.rule,
                            method=', '.join(rule.methods - {'HEAD', 'OPTIONS'}),
                            issue_type='missing_view_function',
                            description=f"No view function found for endpoint: {rule.endpoint}",
                            severity='critical'
                        )
                        self.issues.append(issue)
                        
                except Exception as e:
                    issue = RouteIssue(
                        route=rule.rule,
                        method=', '.join(rule.methods - {'HEAD', 'OPTIONS'}),
                        issue_type='view_function_error',
                        description=f"Error accessing view function for {rule.endpoint}: {e}",
                        severity='high'
                    )
                    self.issues.append(issue)
                    
        except Exception as e:
            logger.error(f"Failed to check route accessibility: {e}")
            self.errors.append(f"Failed to check route accessibility: {e}")
    
    def _check_route_patterns(self):
        """Check route patterns for common issues."""
        try:
            for rule in self.app.url_map.iter_rules():
                # Check for trailing slashes inconsistency
                if rule.rule.endswith('/') and len(rule.rule) > 1:
                    # Check if there's a corresponding route without trailing slash
                    no_slash_rule = rule.rule.rstrip('/')
                    if not any(r.rule == no_slash_rule for r in self.app.url_map.iter_rules()):
                        self.warnings.append(f"Route {rule.rule} has trailing slash but no corresponding route without it")
                
                # Check for overly complex patterns
                if rule.rule.count('<') > 3:
                    issue = RouteIssue(
                        route=rule.rule,
                        method=', '.join(rule.methods - {'HEAD', 'OPTIONS'}),
                        issue_type='complex_pattern',
                        description=f"Route pattern is complex with {rule.rule.count('<')} variables",
                        severity='low'
                    )
                    self.issues.append(issue)
                
                # Check for potential security issues
                if '<path:' in rule.rule:
                    issue = RouteIssue(
                        route=rule.rule,
                        method=', '.join(rule.methods - {'HEAD', 'OPTIONS'}),
                        issue_type='security_concern',
                        description="Route uses path converter which might be a security risk",
                        severity='medium'
                    )
                    self.issues.append(issue)
                    
        except Exception as e:
            logger.error(f"Failed to check route patterns: {e}")
            self.errors.append(f"Failed to check route patterns: {e}")
    
    def _check_endpoint_naming(self):
        """Check endpoint naming conventions."""
        try:
            endpoints = set()
            
            for rule in self.app.url_map.iter_rules():
                endpoint = rule.endpoint
                
                # Check for duplicate endpoints (should not happen but let's verify)
                if endpoint in endpoints:
                    issue = RouteIssue(
                        route=rule.rule,
                        method=', '.join(rule.methods - {'HEAD', 'OPTIONS'}),
                        issue_type='duplicate_endpoint',
                        description=f"Duplicate endpoint name: {endpoint}",
                        severity='critical'
                    )
                    self.issues.append(issue)
                else:
                    endpoints.add(endpoint)
                
                # Check naming conventions
                if not re.match(r'^[a-zA-Z][a-zA-Z0-9_]*(\.[a-zA-Z][a-zA-Z0-9_]*)*$', endpoint):
                    issue = RouteIssue(
                        route=rule.rule,
                        method=', '.join(rule.methods - {'HEAD', 'OPTIONS'}),
                        issue_type='naming_convention',
                        description=f"Endpoint name doesn't follow conventions: {endpoint}",
                        severity='low'
                    )
                    self.issues.append(issue)
                    
        except Exception as e:
            logger.error(f"Failed to check endpoint naming: {e}")
            self.errors.append(f"Failed to check endpoint naming: {e}")
    
    def _check_error_handlers(self):
        """Check for missing error handlers."""
        try:
            error_handlers = self.app.error_handler_spec.get(None, {})
            
            # Check for common HTTP error handlers
            common_errors = [400, 401, 403, 404, 405, 500, 502, 503]
            missing_handlers = []
            
            for error_code in common_errors:
                if error_code not in error_handlers:
                    missing_handlers.append(str(error_code))
            
            if missing_handlers:
                self.warnings.append(f"Missing error handlers for: {', '.join(missing_handlers)}")
                
        except Exception as e:
            logger.error(f"Failed to check error handlers: {e}")
            self.errors.append(f"Failed to check error handlers: {e}")
    
    def get_route_summary(self) -> Dict[str, Any]:
        """Get a summary of all routes."""
        try:
            routes_by_blueprint = defaultdict(list)
            methods_count = defaultdict(int)
            
            for rule in self.app.url_map.iter_rules():
                # Group by blueprint
                blueprint = rule.endpoint.split('.')[0] if '.' in rule.endpoint else 'main'
                routes_by_blueprint[blueprint].append({
                    'rule': rule.rule,
                    'endpoint': rule.endpoint,
                    'methods': list(rule.methods - {'HEAD', 'OPTIONS'})
                })
                
                # Count methods
                for method in rule.methods - {'HEAD', 'OPTIONS'}:
                    methods_count[method] += 1
            
            return {
                'total_routes': len(list(self.app.url_map.iter_rules())),
                'routes_by_blueprint': dict(routes_by_blueprint),
                'methods_count': dict(methods_count),
                'blueprints': list(routes_by_blueprint.keys())
            }
            
        except Exception as e:
            logger.error(f"Failed to get route summary: {e}")
            return {'error': str(e)}
    
    def fix_common_route_issues(self) -> List[str]:
        """Fix common route issues that can be automatically resolved."""
        fixed = []
        
        try:
            # This is a placeholder for automatic fixes
            # In practice, most route issues need manual intervention
            
            # Example: Could add missing error handlers
            self._add_missing_error_handlers()
            fixed.append("Added missing error handlers")
            
        except Exception as e:
            logger.error(f"Failed to fix route issues: {e}")
            self.errors.append(f"Failed to fix route issues: {e}")
        
        self.fixed_issues.extend(fixed)
        return fixed
    
    def _add_missing_error_handlers(self):
        """Add basic error handlers for common HTTP errors."""
        try:
            from flask import jsonify
            
            def create_error_handler(error_code: int):
                def error_handler(error):
                    return jsonify({
                        'error': f'HTTP {error_code}',
                        'message': str(error),
                        'status_code': error_code
                    }), error_code
                return error_handler
            
            # Add handlers for common errors if they don't exist
            common_errors = [400, 401, 403, 404, 405, 500]
            error_handlers = self.app.error_handler_spec.get(None, {})
            
            for error_code in common_errors:
                if error_code not in error_handlers:
                    self.app.errorhandler(error_code)(create_error_handler(error_code))
                    
        except Exception as e:
            logger.warning(f"Could not add error handlers: {e}")
    
    def generate_route_report(self) -> str:
        """Generate a detailed route validation report."""
        try:
            result = self.validate_all_routes()
            summary = self.get_route_summary()
            
            report = []
            report.append("# Route Validation Report")
            report.append(f"Generated: {logger.handlers[0].formatter.formatTime(logger.makeRecord('', 0, '', 0, '', (), None)) if logger.handlers else 'Unknown'}")
            report.append("")
            
            # Summary
            report.append("## Summary")
            report.append(f"- Total Routes: {result.total_routes}")
            report.append(f"- Valid Routes: {result.valid_routes}")
            report.append(f"- Issues Found: {len(result.issues)}")
            report.append(f"- Errors: {len(result.errors)}")
            report.append(f"- Warnings: {len(result.warnings)}")
            report.append("")
            
            # Issues by severity
            if result.issues:
                issues_by_severity = defaultdict(list)
                for issue in result.issues:
                    issues_by_severity[issue.severity].append(issue)
                
                report.append("## Issues by Severity")
                for severity in ['critical', 'high', 'medium', 'low']:
                    if severity in issues_by_severity:
                        report.append(f"### {severity.title()} ({len(issues_by_severity[severity])})")
                        for issue in issues_by_severity[severity]:
                            report.append(f"- **{issue.route}** ({issue.method}): {issue.description}")
                        report.append("")
            
            # Routes by blueprint
            if 'routes_by_blueprint' in summary:
                report.append("## Routes by Blueprint")
                for blueprint, routes in summary['routes_by_blueprint'].items():
                    report.append(f"### {blueprint} ({len(routes)} routes)")
                    for route in routes[:10]:  # Limit to first 10
                        methods = ', '.join(route['methods'])
                        report.append(f"- `{methods}` {route['rule']} → {route['endpoint']}")
                    if len(routes) > 10:
                        report.append(f"- ... and {len(routes) - 10} more")
                    report.append("")
            
            return '\n'.join(report)
            
        except Exception as e:
            logger.error(f"Failed to generate route report: {e}")
            return f"Error generating report: {e}"