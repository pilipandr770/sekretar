"""
Comprehensive Final Report Generator

Creates executive summary with overall system health, detailed issue reports
with reproduction steps, prioritized improvement plan with timelines, and
documents all required user actions with clear instructions.
"""
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from enum import Enum

from tests.infrastructure.models import (
    ComprehensiveReport, TestSuiteResult, Issue, ActionItem, UserAction,
    IssueSeverity, IssueCategory, Priority, Urgency, TestStatus
)


class ReportFormat(Enum):
    """Report output formats."""
    JSON = "json"
    HTML = "html"
    MARKDOWN = "markdown"
    PDF = "pdf"


@dataclass
class ExecutiveSummary:
    """Executive summary data structure."""
    overall_health_score: float  # 0-100
    system_status: str
    total_tests_executed: int
    success_rate: float
    critical_issues_count: int
    high_priority_issues_count: int
    estimated_fix_time: str
    business_impact_assessment: str
    recommendations: List[str]
    next_steps: List[str]


@dataclass
class DetailedIssueReport:
    """Detailed issue report structure."""
    issue: Issue
    business_impact: str
    technical_impact: str
    reproduction_steps: List[str]
    root_cause_analysis: str
    fix_complexity: str
    testing_requirements: List[str]
    rollback_plan: str


@dataclass
class ImprovementPlan:
    """Improvement plan with timelines."""
    action_item: ActionItem
    timeline: str
    resources_required: List[str]
    dependencies: List[str]
    success_metrics: List[str]
    risk_assessment: str
    milestone_checkpoints: List[str]


@dataclass
class UserActionGuide:
    """User action guide with clear instructions."""
    user_action: UserAction
    detailed_instructions: List[str]
    prerequisites: List[str]
    expected_duration: str
    success_indicators: List[str]
    troubleshooting_tips: List[str]
    escalation_contacts: List[str]


class FinalReportGenerator:
    """
    Comprehensive final report generator that creates executive summaries,
    detailed issue reports, prioritized improvement plans, and user action guides.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize final report generator."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Report configuration
        self.output_formats = self.config.get('output_formats', [ReportFormat.HTML, ReportFormat.JSON])
        self.include_charts = self.config.get('include_charts', True)
        self.include_detailed_logs = self.config.get('include_detailed_logs', False)
        
        # Business impact thresholds
        self.impact_thresholds = {
            'critical_threshold': 0.8,  # 80% of critical functionality affected
            'high_threshold': 0.6,      # 60% of high-priority functionality affected
            'medium_threshold': 0.4     # 40% of medium-priority functionality affected
        }
        
        # Timeline estimation factors
        self.timeline_factors = {
            IssueSeverity.CRITICAL: 1.0,    # No delay multiplier
            IssueSeverity.HIGH: 1.2,        # 20% buffer
            IssueSeverity.MEDIUM: 1.5,      # 50% buffer
            IssueSeverity.LOW: 2.0          # 100% buffer
        }
    
    async def generate_comprehensive_final_report(self, 
                                                comprehensive_report: ComprehensiveReport,
                                                execution_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
        """
        Generate comprehensive final report in multiple formats.
        
        Args:
            comprehensive_report: The comprehensive test report
            execution_metadata: Additional execution metadata
            
        Returns:
            Dict mapping format names to file paths
        """
        self.logger.info("Generating comprehensive final report")
        
        # Create reports directory
        reports_dir = Path("final_reports")
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Generate report components
        executive_summary = await self._generate_executive_summary(comprehensive_report)
        detailed_issues = await self._generate_detailed_issue_reports(comprehensive_report.critical_issues)
        improvement_plan = await self._generate_improvement_plan_with_timelines(comprehensive_report.improvement_plan)
        user_action_guides = await self._generate_user_action_guides(comprehensive_report.user_action_required)
        
        # Compile complete report data
        complete_report_data = {
            'metadata': {
                'generation_timestamp': datetime.now().isoformat(),
                'report_version': '1.0',
                'execution_metadata': execution_metadata or {},
                'generator_config': self.config
            },
            'executive_summary': asdict(executive_summary),
            'test_execution_summary': self._create_test_execution_summary(comprehensive_report),
            'detailed_issue_reports': [self._serialize_issue_report(issue_report) for issue_report in detailed_issues],
            'improvement_plan': [self._serialize_improvement_plan(plan) for plan in improvement_plan],
            'user_action_guides': [self._serialize_user_action_guide(guide) for guide in user_action_guides],
            'appendices': {
                'test_suite_results': self._create_test_suite_summary(comprehensive_report.suite_results),
                'performance_metrics': await self._create_performance_summary(comprehensive_report),
                'system_health_indicators': await self._create_system_health_indicators(comprehensive_report)
            }
        }
        
        # Generate reports in requested formats
        generated_files = {}
        
        for format_type in self.output_formats:
            if format_type == ReportFormat.JSON:
                file_path = await self._generate_json_report(complete_report_data, reports_dir, timestamp)
                generated_files['json'] = str(file_path)
            
            elif format_type == ReportFormat.HTML:
                file_path = await self._generate_html_report(complete_report_data, reports_dir, timestamp)
                generated_files['html'] = str(file_path)
            
            elif format_type == ReportFormat.MARKDOWN:
                file_path = await self._generate_markdown_report(complete_report_data, reports_dir, timestamp)
                generated_files['markdown'] = str(file_path)
        
        self.logger.info(f"Generated final reports: {list(generated_files.keys())}")
        return generated_files
    
    def _serialize_issue_report(self, issue_report: DetailedIssueReport) -> Dict[str, Any]:
        """Serialize issue report with proper enum handling."""
        issue_dict = asdict(issue_report)
        
        # Convert enum values to strings
        if 'issue' in issue_dict and 'severity' in issue_dict['issue']:
            issue_dict['issue']['severity'] = {'value': issue_dict['issue']['severity'].value}
        if 'issue' in issue_dict and 'category' in issue_dict['issue']:
            issue_dict['issue']['category'] = {'value': issue_dict['issue']['category'].value}
        
        return issue_dict
    
    def _serialize_improvement_plan(self, plan: ImprovementPlan) -> Dict[str, Any]:
        """Serialize improvement plan with proper enum handling."""
        plan_dict = asdict(plan)
        
        # Convert enum values to strings
        if 'action_item' in plan_dict and 'priority' in plan_dict['action_item']:
            plan_dict['action_item']['priority'] = {'value': plan_dict['action_item']['priority'].value}
        
        return plan_dict
    
    def _serialize_user_action_guide(self, guide: UserActionGuide) -> Dict[str, Any]:
        """Serialize user action guide with proper enum handling."""
        guide_dict = asdict(guide)
        
        # Convert enum values to strings
        if 'user_action' in guide_dict and 'urgency' in guide_dict['user_action']:
            guide_dict['user_action']['urgency'] = {'value': guide_dict['user_action']['urgency'].value}
        
        return guide_dict
    
    async def _generate_executive_summary(self, report: ComprehensiveReport) -> ExecutiveSummary:
        """Generate executive summary with overall system health assessment."""
        self.logger.info("Generating executive summary")
        
        # Calculate overall health score
        health_score = await self._calculate_system_health_score(report)
        
        # Determine system status
        system_status = self._determine_system_status(health_score, report)
        
        # Calculate test statistics
        total_tests = sum(suite.total_tests for suite in report.suite_results)
        total_passed = sum(suite.passed for suite in report.suite_results)
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Count issues by severity
        critical_issues = len([i for i in report.critical_issues if i.severity == IssueSeverity.CRITICAL])
        high_issues = len([i for i in report.critical_issues if i.severity == IssueSeverity.HIGH])
        
        # Estimate total fix time
        estimated_fix_time = self._estimate_total_fix_time(report.critical_issues)
        
        # Assess business impact
        business_impact = await self._assess_business_impact(report)
        
        # Generate recommendations
        recommendations = await self._generate_executive_recommendations(report, health_score)
        
        # Define next steps
        next_steps = await self._define_next_steps(report, critical_issues, high_issues)
        
        return ExecutiveSummary(
            overall_health_score=health_score,
            system_status=system_status,
            total_tests_executed=total_tests,
            success_rate=success_rate,
            critical_issues_count=critical_issues,
            high_priority_issues_count=high_issues,
            estimated_fix_time=estimated_fix_time,
            business_impact_assessment=business_impact,
            recommendations=recommendations,
            next_steps=next_steps
        )
    
    async def _generate_detailed_issue_reports(self, issues: List[Issue]) -> List[DetailedIssueReport]:
        """Generate detailed issue reports with reproduction steps."""
        self.logger.info(f"Generating detailed reports for {len(issues)} issues")
        
        detailed_reports = []
        
        for issue in issues:
            # Assess business and technical impact
            business_impact = await self._assess_issue_business_impact(issue)
            technical_impact = await self._assess_issue_technical_impact(issue)
            
            # Enhance reproduction steps
            enhanced_steps = await self._enhance_reproduction_steps(issue)
            
            # Perform root cause analysis
            root_cause = await self._perform_root_cause_analysis(issue)
            
            # Assess fix complexity
            fix_complexity = await self._assess_fix_complexity(issue)
            
            # Define testing requirements
            testing_requirements = await self._define_testing_requirements(issue)
            
            # Create rollback plan
            rollback_plan = await self._create_rollback_plan(issue)
            
            detailed_report = DetailedIssueReport(
                issue=issue,
                business_impact=business_impact,
                technical_impact=technical_impact,
                reproduction_steps=enhanced_steps,
                root_cause_analysis=root_cause,
                fix_complexity=fix_complexity,
                testing_requirements=testing_requirements,
                rollback_plan=rollback_plan
            )
            
            detailed_reports.append(detailed_report)
        
        return detailed_reports
    
    async def _generate_improvement_plan_with_timelines(self, action_items: List[ActionItem]) -> List[ImprovementPlan]:
        """Generate improvement plan with detailed timelines."""
        self.logger.info(f"Generating improvement plan for {len(action_items)} action items")
        
        improvement_plans = []
        
        for action_item in action_items:
            # Calculate realistic timeline
            timeline = await self._calculate_realistic_timeline(action_item)
            
            # Identify required resources
            resources = await self._identify_required_resources(action_item)
            
            # Map dependencies
            dependencies = await self._map_action_dependencies(action_item, action_items)
            
            # Define success metrics
            success_metrics = await self._define_success_metrics(action_item)
            
            # Assess risks
            risk_assessment = await self._assess_action_risks(action_item)
            
            # Create milestone checkpoints
            milestones = await self._create_milestone_checkpoints(action_item, timeline)
            
            improvement_plan = ImprovementPlan(
                action_item=action_item,
                timeline=timeline,
                resources_required=resources,
                dependencies=dependencies,
                success_metrics=success_metrics,
                risk_assessment=risk_assessment,
                milestone_checkpoints=milestones
            )
            
            improvement_plans.append(improvement_plan)
        
        return improvement_plans
    
    async def _generate_user_action_guides(self, user_actions: List[UserAction]) -> List[UserActionGuide]:
        """Generate user action guides with clear instructions."""
        self.logger.info(f"Generating user action guides for {len(user_actions)} actions")
        
        action_guides = []
        
        for user_action in user_actions:
            # Create detailed instructions
            detailed_instructions = await self._create_detailed_instructions(user_action)
            
            # Identify prerequisites
            prerequisites = await self._identify_prerequisites(user_action)
            
            # Estimate duration
            duration = await self._estimate_action_duration(user_action)
            
            # Define success indicators
            success_indicators = await self._define_success_indicators(user_action)
            
            # Create troubleshooting tips
            troubleshooting_tips = await self._create_troubleshooting_tips(user_action)
            
            # Identify escalation contacts
            escalation_contacts = await self._identify_escalation_contacts(user_action)
            
            action_guide = UserActionGuide(
                user_action=user_action,
                detailed_instructions=detailed_instructions,
                prerequisites=prerequisites,
                expected_duration=duration,
                success_indicators=success_indicators,
                troubleshooting_tips=troubleshooting_tips,
                escalation_contacts=escalation_contacts
            )
            
            action_guides.append(action_guide)
        
        return action_guides
    
    async def _calculate_system_health_score(self, report: ComprehensiveReport) -> float:
        """Calculate overall system health score (0-100)."""
        if not report.suite_results:
            return 0.0
        
        # Base score from test success rate
        total_tests = sum(suite.total_tests for suite in report.suite_results)
        total_passed = sum(suite.passed for suite in report.suite_results)
        base_score = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        # Apply penalties for critical issues
        critical_issues = len([i for i in report.critical_issues if i.severity == IssueSeverity.CRITICAL])
        high_issues = len([i for i in report.critical_issues if i.severity == IssueSeverity.HIGH])
        
        # Penalty calculation
        critical_penalty = critical_issues * 15  # 15 points per critical issue
        high_penalty = high_issues * 5          # 5 points per high issue
        
        # Calculate final score
        final_score = max(0, base_score - critical_penalty - high_penalty)
        
        return min(100, final_score)
    
    def _determine_system_status(self, health_score: float, report: ComprehensiveReport) -> str:
        """Determine system status based on health score and issues."""
        critical_issues = len([i for i in report.critical_issues if i.severity == IssueSeverity.CRITICAL])
        
        if critical_issues > 0:
            return "CRITICAL - Immediate Action Required"
        elif health_score >= 90:
            return "EXCELLENT - System Operating Optimally"
        elif health_score >= 75:
            return "GOOD - Minor Issues Detected"
        elif health_score >= 50:
            return "FAIR - Multiple Issues Need Attention"
        else:
            return "POOR - Significant Issues Detected"
    
    def _estimate_total_fix_time(self, issues: List[Issue]) -> str:
        """Estimate total time required to fix all issues."""
        if not issues:
            return "No fixes required"
        
        # Parse effort estimates and sum them
        total_hours = 0
        
        for issue in issues:
            effort = issue.estimated_effort
            if "hour" in effort.lower():
                # Extract hours from strings like "2-4 hours", "1 hour"
                import re
                hours_match = re.findall(r'(\d+)', effort)
                if hours_match:
                    # Take the maximum if range is given
                    hours = max(int(h) for h in hours_match)
                    total_hours += hours
        
        if total_hours == 0:
            return "Effort estimation pending"
        
        # Convert to days/weeks for better readability
        if total_hours <= 8:
            return f"{total_hours} hours"
        elif total_hours <= 40:
            days = total_hours / 8
            return f"{days:.1f} days"
        else:
            weeks = total_hours / 40
            return f"{weeks:.1f} weeks"
    
    async def _assess_business_impact(self, report: ComprehensiveReport) -> str:
        """Assess overall business impact of detected issues."""
        critical_issues = [i for i in report.critical_issues if i.severity == IssueSeverity.CRITICAL]
        high_issues = [i for i in report.critical_issues if i.severity == IssueSeverity.HIGH]
        
        # Analyze affected components
        affected_components = set()
        for issue in report.critical_issues:
            affected_components.update(issue.affected_components)
        
        # Determine business impact level
        if len(critical_issues) > 5:
            return "SEVERE - Multiple critical systems affected, potential service disruption"
        elif len(critical_issues) > 0:
            return "HIGH - Critical functionality compromised, user experience impacted"
        elif len(high_issues) > 10:
            return "MODERATE - Multiple high-priority issues may affect system reliability"
        elif len(high_issues) > 0:
            return "LOW - Some functionality issues detected, minimal user impact"
        else:
            return "MINIMAL - No significant business impact detected"
    
    async def _generate_executive_recommendations(self, report: ComprehensiveReport, health_score: float) -> List[str]:
        """Generate executive-level recommendations."""
        recommendations = []
        
        critical_issues = len([i for i in report.critical_issues if i.severity == IssueSeverity.CRITICAL])
        
        if critical_issues > 0:
            recommendations.append("Immediately address all critical issues before production deployment")
            recommendations.append("Establish incident response team for critical issue resolution")
        
        if health_score < 75:
            recommendations.append("Implement comprehensive quality assurance process")
            recommendations.append("Increase test coverage for affected components")
        
        if len(report.critical_issues) > 20:
            recommendations.append("Consider code review and refactoring initiative")
            recommendations.append("Evaluate development process improvements")
        
        # Always include these
        recommendations.extend([
            "Establish regular automated testing schedule",
            "Implement continuous monitoring for early issue detection",
            "Create documentation for identified fixes and improvements"
        ])
        
        return recommendations
    
    async def _define_next_steps(self, report: ComprehensiveReport, critical_count: int, high_count: int) -> List[str]:
        """Define immediate next steps."""
        next_steps = []
        
        if critical_count > 0:
            next_steps.extend([
                "1. IMMEDIATE: Review and triage all critical issues",
                "2. IMMEDIATE: Assign critical issues to development team",
                "3. TODAY: Begin fixing highest priority critical issues"
            ])
        
        if high_count > 0:
            next_steps.extend([
                f"4. THIS WEEK: Address {min(5, high_count)} high-priority issues",
                "5. THIS WEEK: Implement fixes for authentication/security issues"
            ])
        
        next_steps.extend([
            "6. NEXT WEEK: Re-run comprehensive test suite",
            "7. NEXT WEEK: Review and update testing procedures",
            "8. ONGOING: Monitor system health metrics"
        ])
        
        return next_steps  
  
    # Issue analysis methods
    async def _assess_issue_business_impact(self, issue: Issue) -> str:
        """Assess business impact of a specific issue."""
        if issue.severity == IssueSeverity.CRITICAL:
            if 'authentication' in issue.title.lower() or 'security' in issue.title.lower():
                return "CRITICAL - Security vulnerability may expose user data or system access"
            elif 'api' in issue.title.lower() or 'endpoint' in issue.title.lower():
                return "HIGH - API failures may prevent core functionality and user access"
            else:
                return "HIGH - Critical system component failure affects core business operations"
        
        elif issue.severity == IssueSeverity.HIGH:
            return "MEDIUM - Functionality issues may degrade user experience and system reliability"
        
        else:
            return "LOW - Minor issues with minimal impact on business operations"
    
    async def _assess_issue_technical_impact(self, issue: Issue) -> str:
        """Assess technical impact of a specific issue."""
        affected_systems = len(issue.affected_components)
        
        if affected_systems > 3:
            return f"WIDESPREAD - Affects {affected_systems} system components, may require coordinated fixes"
        elif affected_systems > 1:
            return f"MODERATE - Affects {affected_systems} components, requires integration testing"
        else:
            return "LOCALIZED - Isolated to single component, straightforward to fix"
    
    async def _enhance_reproduction_steps(self, issue: Issue) -> List[str]:
        """Enhance reproduction steps with additional context."""
        enhanced_steps = ["Prerequisites:", "- Ensure test environment is properly configured", "- Verify all required services are running", ""]
        enhanced_steps.extend(["Reproduction Steps:"] + issue.reproduction_steps)
        enhanced_steps.extend(["", "Expected Result:", issue.expected_behavior, "", "Actual Result:", issue.actual_behavior])
        return enhanced_steps
    
    async def _perform_root_cause_analysis(self, issue: Issue) -> str:
        """Perform root cause analysis for an issue."""
        # Simple heuristic-based root cause analysis
        title_lower = issue.title.lower()
        description_lower = issue.description.lower()
        
        if 'authentication' in title_lower or 'login' in title_lower:
            return "Root cause likely related to authentication service configuration or token management"
        elif 'database' in description_lower or 'sql' in description_lower:
            return "Root cause likely related to database connectivity, schema, or query optimization"
        elif 'api' in title_lower or 'endpoint' in title_lower:
            return "Root cause likely related to API endpoint configuration, validation, or error handling"
        elif 'timeout' in description_lower or 'performance' in description_lower:
            return "Root cause likely related to system performance, resource constraints, or network latency"
        else:
            return "Root cause requires detailed investigation of system logs and component interactions"
    
    async def _assess_fix_complexity(self, issue: Issue) -> str:
        """Assess the complexity of fixing an issue."""
        if issue.severity == IssueSeverity.CRITICAL and len(issue.affected_components) > 2:
            return "HIGH - Complex fix requiring coordination across multiple components"
        elif 'integration' in issue.title.lower() or len(issue.affected_components) > 1:
            return "MEDIUM - Moderate complexity requiring integration testing"
        else:
            return "LOW - Straightforward fix with minimal dependencies"
    
    async def _define_testing_requirements(self, issue: Issue) -> List[str]:
        """Define testing requirements for issue fix."""
        requirements = [
            "Unit tests for affected components",
            "Integration tests for component interactions"
        ]
        
        if issue.severity == IssueSeverity.CRITICAL:
            requirements.extend([
                "End-to-end testing of complete user workflows",
                "Security testing if authentication/authorization affected",
                "Performance testing under load"
            ])
        
        if len(issue.affected_components) > 1:
            requirements.append("Cross-component integration testing")
        
        requirements.append("Regression testing of related functionality")
        return requirements
    
    async def _create_rollback_plan(self, issue: Issue) -> str:
        """Create rollback plan for issue fix."""
        if issue.severity == IssueSeverity.CRITICAL:
            return ("1. Immediately revert code changes if issues detected\n"
                   "2. Restore database backup if schema changes involved\n"
                   "3. Restart affected services\n"
                   "4. Verify system functionality\n"
                   "5. Notify stakeholders of rollback")
        else:
            return ("1. Revert code changes using version control\n"
                   "2. Restart affected services if needed\n"
                   "3. Run smoke tests to verify system stability")
    
    # Timeline and resource planning methods
    async def _calculate_realistic_timeline(self, action_item: ActionItem) -> str:
        """Calculate realistic timeline for action item."""
        base_time = action_item.estimated_time
        
        # Apply complexity multipliers
        if len(action_item.dependencies) > 2:
            return f"{base_time} (extended due to dependencies)"
        elif action_item.priority == Priority.HIGH:
            return f"{base_time} (expedited)"
        else:
            return base_time
    
    async def _identify_required_resources(self, action_item: ActionItem) -> List[str]:
        """Identify resources required for action item."""
        resources = ["Development team member"]
        
        if 'security' in action_item.title.lower():
            resources.append("Security specialist")
        
        if 'database' in action_item.description.lower():
            resources.append("Database administrator")
        
        if 'integration' in action_item.description.lower():
            resources.append("Integration testing environment")
        
        if action_item.priority == Priority.HIGH:
            resources.append("Senior developer for code review")
        
        return resources  
  
    async def _map_action_dependencies(self, action_item: ActionItem, all_actions: List[ActionItem]) -> List[str]:
        """Map dependencies between action items."""
        dependencies = action_item.dependencies.copy()
        
        # Add implicit dependencies based on content analysis
        for other_action in all_actions:
            if (other_action.id != action_item.id and 
                any(component in other_action.description.lower() 
                    for component in action_item.description.lower().split()[:5])):
                dependencies.append(f"Coordinate with: {other_action.title}")
        
        return dependencies
    
    async def _define_success_metrics(self, action_item: ActionItem) -> List[str]:
        """Define success metrics for action item."""
        metrics = action_item.acceptance_criteria.copy()
        
        # Add standard metrics
        metrics.extend([
            "All related tests pass successfully",
            "No regression in existing functionality",
            "Code review approval received"
        ])
        
        if 'performance' in action_item.description.lower():
            metrics.append("Performance benchmarks meet requirements")
        
        return metrics
    
    async def _assess_action_risks(self, action_item: ActionItem) -> str:
        """Assess risks associated with action item."""
        if action_item.priority == Priority.HIGH and len(action_item.dependencies) > 2:
            return "HIGH - Complex high-priority fix with multiple dependencies may introduce regressions"
        elif 'security' in action_item.title.lower():
            return "MEDIUM - Security-related changes require careful testing to avoid vulnerabilities"
        elif len(action_item.dependencies) > 1:
            return "MEDIUM - Multiple dependencies may cause delays or coordination issues"
        else:
            return "LOW - Straightforward fix with minimal risk of complications"
    
    async def _create_milestone_checkpoints(self, action_item: ActionItem, timeline: str) -> List[str]:
        """Create milestone checkpoints for action item."""
        milestones = [
            "25% - Initial analysis and design completed",
            "50% - Core implementation completed",
            "75% - Testing and validation completed",
            "100% - Code review and deployment ready"
        ]
        
        if action_item.priority == Priority.HIGH:
            milestones.insert(1, "Daily progress check-ins scheduled")
        
        return milestones
    
    # User action guide methods
    async def _create_detailed_instructions(self, user_action: UserAction) -> List[str]:
        """Create detailed step-by-step instructions."""
        detailed_instructions = ["DETAILED STEP-BY-STEP INSTRUCTIONS:", ""]
        
        for i, instruction in enumerate(user_action.instructions, 1):
            detailed_instructions.extend([
                f"Step {i}: {instruction}",
                f"  - Take your time to complete this step thoroughly",
                f"  - Verify completion before proceeding to next step",
                ""
            ])
        
        detailed_instructions.extend([
            "COMPLETION VERIFICATION:",
            f"- Confirm that: {user_action.expected_outcome}",
            "- Document any issues encountered during execution"
        ])
        
        return detailed_instructions
    
    async def _identify_prerequisites(self, user_action: UserAction) -> List[str]:
        """Identify prerequisites for user action."""
        prerequisites = [
            "Administrative access to the system",
            "Backup of current system state completed"
        ]
        
        if user_action.urgency == Urgency.IMMEDIATE:
            prerequisites.insert(0, "Immediate availability of responsible team member")
        
        if 'database' in user_action.description.lower():
            prerequisites.append("Database access credentials")
        
        if 'deployment' in user_action.description.lower():
            prerequisites.append("Deployment environment access")
        
        return prerequisites
    
    async def _estimate_action_duration(self, user_action: UserAction) -> str:
        """Estimate duration for user action."""
        if user_action.urgency == Urgency.IMMEDIATE:
            return "15-30 minutes (immediate attention required)"
        elif len(user_action.instructions) > 5:
            return "1-2 hours (complex multi-step process)"
        else:
            return "30-60 minutes (standard process)"
    
    async def _define_success_indicators(self, user_action: UserAction) -> List[str]:
        """Define success indicators for user action."""
        indicators = [
            user_action.expected_outcome,
            "No error messages or warnings displayed",
            "System functionality verified as working"
        ]
        
        if 'fix' in user_action.title.lower():
            indicators.append("Related test cases now pass successfully")
        
        return indicators
    
    async def _create_troubleshooting_tips(self, user_action: UserAction) -> List[str]:
        """Create troubleshooting tips for user action."""
        tips = [
            "If you encounter errors, check system logs for detailed error messages",
            "Ensure all prerequisites are met before starting",
            "Take screenshots of any error messages for support team"
        ]
        
        if user_action.urgency == Urgency.IMMEDIATE:
            tips.insert(0, "If action fails, immediately escalate to technical team")
        
        return tips
    
    async def _identify_escalation_contacts(self, user_action: UserAction) -> List[str]:
        """Identify escalation contacts for user action."""
        contacts = [
            "Technical Lead - for implementation questions",
            "System Administrator - for access or permission issues"
        ]
        
        if user_action.urgency == Urgency.IMMEDIATE:
            contacts.insert(0, "On-call Engineer - for immediate critical issues")
        
        if 'security' in user_action.description.lower():
            contacts.append("Security Team - for security-related concerns")
        
        return contacts    
  
  # Report generation methods
    def _create_test_execution_summary(self, report: ComprehensiveReport) -> Dict[str, Any]:
        """Create test execution summary."""
        total_tests = sum(suite.total_tests for suite in report.suite_results)
        total_passed = sum(suite.passed for suite in report.suite_results)
        total_failed = sum(suite.failed for suite in report.suite_results)
        total_errors = sum(suite.errors for suite in report.suite_results)
        
        return {
            'total_tests': total_tests,
            'passed': total_passed,
            'failed': total_failed,
            'errors': total_errors,
            'success_rate': (total_passed / total_tests * 100) if total_tests > 0 else 0,
            'execution_time': report.total_execution_time,
            'suites_executed': len(report.suite_results)
        }
    
    def _create_test_suite_summary(self, suite_results: List[TestSuiteResult]) -> List[Dict[str, Any]]:
        """Create test suite summary."""
        return [
            {
                'suite_name': suite.suite_name,
                'total_tests': suite.total_tests,
                'passed': suite.passed,
                'failed': suite.failed,
                'errors': suite.errors,
                'success_rate': (suite.passed / suite.total_tests * 100) if suite.total_tests > 0 else 0,
                'execution_time': suite.execution_time
            }
            for suite in suite_results
        ]
    
    async def _create_performance_summary(self, report: ComprehensiveReport) -> Dict[str, Any]:
        """Create performance metrics summary."""
        return {
            'total_execution_time': report.total_execution_time,
            'average_test_time': report.total_execution_time / max(1, sum(suite.total_tests for suite in report.suite_results)),
            'slowest_suite': max(report.suite_results, key=lambda s: s.execution_time).suite_name if report.suite_results else None,
            'performance_issues_detected': len([i for i in report.critical_issues if 'performance' in i.title.lower()])
        }
    
    async def _create_system_health_indicators(self, report: ComprehensiveReport) -> Dict[str, Any]:
        """Create system health indicators."""
        return {
            'overall_health_score': await self._calculate_system_health_score(report),
            'critical_issues_count': len([i for i in report.critical_issues if i.severity == IssueSeverity.CRITICAL]),
            'high_issues_count': len([i for i in report.critical_issues if i.severity == IssueSeverity.HIGH]),
            'affected_components': list(set(comp for issue in report.critical_issues for comp in issue.affected_components)),
            'system_status': self._determine_system_status(await self._calculate_system_health_score(report), report)
        }
    
    # File generation methods
    async def _generate_json_report(self, report_data: Dict[str, Any], reports_dir: Path, timestamp: str) -> Path:
        """Generate JSON format report."""
        file_path = reports_dir / f"comprehensive_final_report_{timestamp}.json"
        
        with open(file_path, 'w') as f:
            json.dump(report_data, f, indent=2, default=str)
        
        self.logger.info(f"Generated JSON report: {file_path}")
        return file_path
    
    async def _generate_html_report(self, report_data: Dict[str, Any], reports_dir: Path, timestamp: str) -> Path:
        """Generate HTML format report."""
        file_path = reports_dir / f"comprehensive_final_report_{timestamp}.html"
        
        # Create a simplified HTML report
        html_content = self._create_html_content(report_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        self.logger.info(f"Generated HTML report: {file_path}")
        return file_path
    
    async def _generate_markdown_report(self, report_data: Dict[str, Any], reports_dir: Path, timestamp: str) -> Path:
        """Generate Markdown format report."""
        file_path = reports_dir / f"comprehensive_final_report_{timestamp}.md"
        
        # Generate markdown content
        markdown_content = self._create_markdown_content(report_data)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(markdown_content)
        
        self.logger.info(f"Generated Markdown report: {file_path}")
        return file_path
    
    def _create_html_content(self, report_data: Dict[str, Any]) -> str:
        """Create HTML content for the report."""
        exec_summary = report_data.get('executive_summary', {})
        test_summary = report_data.get('test_execution_summary', {})
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Comprehensive Test Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
        .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
        .section {{ margin-bottom: 30px; }}
        .critical {{ color: #d32f2f; font-weight: bold; }}
        .high {{ color: #f57c00; font-weight: bold; }}
        .success {{ color: #388e3c; font-weight: bold; }}
        .issue {{ border-left: 4px solid #d32f2f; padding-left: 15px; margin: 10px 0; }}
        .action {{ border-left: 4px solid #1976d2; padding-left: 15px; margin: 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .progress-bar {{ width: 100%; background-color: #f0f0f0; border-radius: 3px; }}
        .progress-fill {{ height: 20px; background-color: #4caf50; border-radius: 3px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Comprehensive System Test Report</h1>
        <p><strong>Generated:</strong> {report_data.get('metadata', {}).get('generation_timestamp', '')}</p>
        <p><strong>System Status:</strong> <span class="critical">{exec_summary.get('system_status', 'Unknown')}</span></p>
        <p><strong>Health Score:</strong> {exec_summary.get('overall_health_score', 0):.1f}/100</p>
    </div>

    <div class="section">
        <h2>Executive Summary</h2>
        <div class="progress-bar">
            <div class="progress-fill" style="width: {exec_summary.get('overall_health_score', 0)}%"></div>
        </div>
        <p><strong>Tests Executed:</strong> {exec_summary.get('total_tests_executed', 0)}</p>
        <p><strong>Success Rate:</strong> {exec_summary.get('success_rate', 0):.1f}%</p>
        <p><strong>Critical Issues:</strong> <span class="critical">{exec_summary.get('critical_issues_count', 0)}</span></p>
        <p><strong>High Priority Issues:</strong> <span class="high">{exec_summary.get('high_priority_issues_count', 0)}</span></p>
        <p><strong>Estimated Fix Time:</strong> {exec_summary.get('estimated_fix_time', 'Unknown')}</p>
        
        <h3>Business Impact Assessment</h3>
        <p>{exec_summary.get('business_impact_assessment', 'No assessment available')}</p>
        
        <h3>Recommendations</h3>
        <ul>
"""
        
        for rec in exec_summary.get('recommendations', []):
            html_content += f"            <li>{rec}</li>\n"
        
        html_content += """        </ul>
        
        <h3>Next Steps</h3>
        <ol>
"""
        
        for step in exec_summary.get('next_steps', []):
            html_content += f"            <li>{step}</li>\n"
        
        html_content += f"""        </ol>
    </div>

    <div class="section">
        <h2>Test Suite Results</h2>
        <table>
            <tr>
                <th>Suite Name</th>
                <th>Total Tests</th>
                <th>Passed</th>
                <th>Failed</th>
                <th>Errors</th>
                <th>Success Rate</th>
                <th>Execution Time</th>
            </tr>
"""
        
        for suite in report_data.get('appendices', {}).get('test_suite_results', []):
            html_content += f"""            <tr>
                <td>{suite.get('suite_name', '')}</td>
                <td>{suite.get('total_tests', 0)}</td>
                <td class="success">{suite.get('passed', 0)}</td>
                <td class="high">{suite.get('failed', 0)}</td>
                <td class="critical">{suite.get('errors', 0)}</td>
                <td>{suite.get('success_rate', 0):.1f}%</td>
                <td>{suite.get('execution_time', 0):.2f}s</td>
            </tr>
"""
        
        html_content += """        </table>
    </div>

    <div class="section">
        <h2>Critical Issues</h2>
"""
        
        for issue_report in report_data.get('detailed_issue_reports', []):
            issue = issue_report.get('issue', {})
            html_content += f"""        <div class="issue">
            <h3>{issue.get('title', 'Unknown Issue')}</h3>
            <p><strong>Severity:</strong> <span class="critical">{issue.get('severity', 'unknown').upper() if isinstance(issue.get('severity'), str) else getattr(issue.get('severity', {}), 'value', 'unknown').upper()}</span></p>
            <p><strong>Category:</strong> {issue.get('category', 'unknown').title() if isinstance(issue.get('category'), str) else getattr(issue.get('category', {}), 'value', 'unknown').title()}</p>
            <p><strong>Description:</strong> {issue.get('description', 'No description')}</p>
            <p><strong>Business Impact:</strong> {issue_report.get('business_impact', 'Unknown')}</p>
            <p><strong>Technical Impact:</strong> {issue_report.get('technical_impact', 'Unknown')}</p>
            <p><strong>Fix Complexity:</strong> {issue_report.get('fix_complexity', 'Unknown')}</p>
            <p><strong>Estimated Effort:</strong> {issue.get('estimated_effort', 'Unknown')}</p>
        </div>
"""
        
        html_content += """    </div>
</body>
</html>
        """
        
        return html_content
    
    def _create_markdown_content(self, report_data: Dict[str, Any]) -> str:
        """Create markdown content for the report."""
        exec_summary = report_data.get('executive_summary', {})
        test_summary = report_data.get('test_execution_summary', {})
        
        content = f"""# Comprehensive System Test Report

**Generated:** {report_data.get('metadata', {}).get('generation_timestamp', '')}
**Report Version:** {report_data.get('metadata', {}).get('report_version', '1.0')}

## Executive Summary

### System Status: {exec_summary.get('system_status', 'Unknown')}
### Health Score: {exec_summary.get('overall_health_score', 0):.1f}/100

- **Tests Executed:** {exec_summary.get('total_tests_executed', 0)}
- **Success Rate:** {exec_summary.get('success_rate', 0):.1f}%
- **Critical Issues:** {exec_summary.get('critical_issues_count', 0)}
- **High Priority Issues:** {exec_summary.get('high_priority_issues_count', 0)}
- **Estimated Fix Time:** {exec_summary.get('estimated_fix_time', 'Unknown')}

### Business Impact Assessment
{exec_summary.get('business_impact_assessment', 'No assessment available')}

### Recommendations
"""
        
        for rec in exec_summary.get('recommendations', []):
            content += f"- {rec}\n"
        
        content += "\n### Next Steps\n"
        for i, step in enumerate(exec_summary.get('next_steps', []), 1):
            content += f"{i}. {step}\n"
        
        content += "\n## Test Execution Summary\n\n"
        content += f"| Metric | Value |\n"
        content += f"|--------|-------|\n"
        content += f"| Total Tests | {test_summary.get('total_tests', 0)} |\n"
        content += f"| Passed | {test_summary.get('passed', 0)} |\n"
        content += f"| Failed | {test_summary.get('failed', 0)} |\n"
        content += f"| Errors | {test_summary.get('errors', 0)} |\n"
        content += f"| Success Rate | {test_summary.get('success_rate', 0):.1f}% |\n"
        content += f"| Execution Time | {test_summary.get('execution_time', 0):.2f}s |\n"
        
        # Add detailed issues
        content += "\n## Critical Issues\n\n"
        for issue_report in report_data.get('detailed_issue_reports', []):
            issue = issue_report.get('issue', {})
            content += f"### {issue.get('title', 'Unknown Issue')}\n\n"
            content += f"- **Severity:** {issue.get('severity', {}).get('value', 'unknown').upper()}\n"
            content += f"- **Category:** {issue.get('category', {}).get('value', 'unknown').title()}\n"
            content += f"- **Description:** {issue.get('description', 'No description')}\n"
            content += f"- **Business Impact:** {issue_report.get('business_impact', 'Unknown')}\n"
            content += f"- **Technical Impact:** {issue_report.get('technical_impact', 'Unknown')}\n"
            content += f"- **Fix Complexity:** {issue_report.get('fix_complexity', 'Unknown')}\n"
            content += f"- **Estimated Effort:** {issue.get('estimated_effort', 'Unknown')}\n\n"
        
        # Add improvement plan
        content += "\n## Improvement Plan\n\n"
        for plan in report_data.get('improvement_plan', []):
            action = plan.get('action_item', {})
            content += f"### {action.get('title', 'Unknown Action')}\n\n"
            content += f"- **Priority:** {action.get('priority', {}).get('value', 'unknown').upper()}\n"
            content += f"- **Timeline:** {plan.get('timeline', 'Unknown')}\n"
            content += f"- **Assigned To:** {action.get('assigned_to', 'Unknown')}\n"
            content += f"- **Description:** {action.get('description', 'No description')}\n\n"
        
        # Add user actions
        content += "\n## User Actions Required\n\n"
        for guide in report_data.get('user_action_guides', []):
            user_action = guide.get('user_action', {})
            content += f"### {user_action.get('title', 'Unknown Action')}\n\n"
            content += f"- **Urgency:** {user_action.get('urgency', {}).get('value', 'unknown').upper()}\n"
            content += f"- **Expected Duration:** {guide.get('expected_duration', 'Unknown')}\n"
            content += f"- **Description:** {user_action.get('description', 'No description')}\n\n"
            
            content += "#### Instructions:\n"
            for instruction in user_action.get('instructions', []):
                content += f"1. {instruction}\n"
            content += "\n"
        
        return content


# CLI interface for standalone usage
async def main():
    """Main function for standalone report generation."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Generate comprehensive final test report')
    parser.add_argument('--input', required=True, help='Path to comprehensive report JSON file')
    parser.add_argument('--output-dir', default='final_reports', help='Output directory for reports')
    parser.add_argument('--formats', nargs='+', choices=['json', 'html', 'markdown'], 
                       default=['html', 'json'], help='Output formats')
    
    args = parser.parse_args()
    
    # Load input report
    try:
        with open(args.input, 'r') as f:
            report_data = json.load(f)
        
        # Convert to ComprehensiveReport object (simplified)
        # In real usage, this would properly deserialize the object
        comprehensive_report = type('ComprehensiveReport', (), report_data)()
        
    except Exception as e:
        print(f"Error loading input report: {e}")
        sys.exit(1)
    
    # Configure generator
    config = {
        'output_formats': [ReportFormat(fmt) for fmt in args.formats],
        'include_charts': True,
        'include_detailed_logs': True
    }
    
    # Generate report
    generator = FinalReportGenerator(config)
    
    try:
        generated_files = await generator.generate_comprehensive_final_report(
            comprehensive_report,
            {'cli_execution': True, 'input_file': args.input}
        )
        
        print("Generated reports:")
        for format_name, file_path in generated_files.items():
            print(f"  {format_name.upper()}: {file_path}")
        
    except Exception as e:
        print(f"Error generating report: {e}")
        sys.exit(1)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())