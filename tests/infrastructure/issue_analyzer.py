"""
Issue Identification and Prioritization System

Implements critical issue detection algorithms, severity and impact assessment,
and fix priority calculation system for comprehensive testing framework.
"""
import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from enum import Enum

from tests.infrastructure.models import (
    Issue, IssueSeverity, IssueCategory, TestResult, TestSuiteResult,
    TestStatus, ActionItem, Priority, UserAction, Urgency
)
from tests.infrastructure.test_result_collector import ErrorAnalysis, PerformanceAnalysis


class ImpactLevel(Enum):
    """Impact levels for issue assessment."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ComponentCriticality(Enum):
    """Criticality levels for system components."""
    CORE = "core"  # Authentication, billing, core business logic
    IMPORTANT = "important"  # CRM, KYB, integrations
    SUPPORTING = "supporting"  # Monitoring, logging, utilities
    OPTIONAL = "optional"  # Nice-to-have features


@dataclass
class IssueContext:
    """Context information for issue analysis."""
    affected_users: int
    business_impact: str
    component_criticality: ComponentCriticality
    frequency: int
    trend: str  # INCREASING, STABLE, DECREASING
    related_issues: List[str]
    external_dependencies: List[str]


@dataclass
class PriorityScore:
    """Priority scoring breakdown."""
    severity_score: float
    impact_score: float
    frequency_score: float
    trend_score: float
    component_score: float
    total_score: float
    priority_level: Priority


class IssueAnalyzer:
    """
    Advanced issue identification and prioritization system.
    
    Analyzes test results, performance data, and error patterns to identify
    critical issues, assess their severity and impact, and calculate fix priorities.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize issue analyzer."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Issue detection configuration
        self.detection_thresholds = {
            'critical_error_rate': self.config.get('critical_error_rate', 0.10),  # 10%
            'high_error_rate': self.config.get('high_error_rate', 0.05),  # 5%
            'critical_response_time': self.config.get('critical_response_time', 10.0),  # 10 seconds
            'high_response_time': self.config.get('high_response_time', 5.0),  # 5 seconds
            'frequent_error_threshold': self.config.get('frequent_error_threshold', 10),  # occurrences
            'performance_degradation_threshold': self.config.get('performance_degradation_threshold', 2.0)  # 2x baseline
        }
        
        # Component criticality mapping
        self.component_criticality_map = {
            'auth': ComponentCriticality.CORE,
            'authentication': ComponentCriticality.CORE,
            'billing': ComponentCriticality.CORE,
            'subscription': ComponentCriticality.CORE,
            'tenant': ComponentCriticality.CORE,
            'crm': ComponentCriticality.IMPORTANT,
            'kyb': ComponentCriticality.IMPORTANT,
            'calendar': ComponentCriticality.IMPORTANT,
            'knowledge': ComponentCriticality.IMPORTANT,
            'telegram': ComponentCriticality.SUPPORTING,
            'signal': ComponentCriticality.SUPPORTING,
            'monitoring': ComponentCriticality.SUPPORTING,
            'logging': ComponentCriticality.SUPPORTING,
            'web_widget': ComponentCriticality.OPTIONAL,
            'demo': ComponentCriticality.OPTIONAL
        }
        
        # Priority scoring weights
        self.scoring_weights = {
            'severity': self.config.get('severity_weight', 0.30),
            'impact': self.config.get('impact_weight', 0.25),
            'frequency': self.config.get('frequency_weight', 0.20),
            'trend': self.config.get('trend_weight', 0.15),
            'component': self.config.get('component_weight', 0.10)
        }
        
        # Issue tracking
        self.identified_issues: List[Issue] = []
        self.issue_contexts: Dict[str, IssueContext] = {}
        self.priority_scores: Dict[str, PriorityScore] = {}
    
    async def analyze_test_results(self, test_results: List[TestResult], 
                                 suite_results: List[TestSuiteResult],
                                 error_analyses: List[ErrorAnalysis],
                                 performance_analyses: List[PerformanceAnalysis]) -> List[Issue]:
        """
        Comprehensive analysis of test results to identify critical issues.
        
        Args:
            test_results: Individual test results
            suite_results: Test suite results
            error_analyses: Error pattern analyses
            performance_analyses: Performance analyses
            
        Returns:
            List of identified issues with severity and priority
        """
        self.logger.info("Starting comprehensive issue analysis")
        
        # Clear previous analysis
        self.identified_issues.clear()
        self.issue_contexts.clear()
        self.priority_scores.clear()
        
        # Analyze different types of issues
        functionality_issues = await self._detect_functionality_issues(test_results, suite_results)
        performance_issues = await self._detect_performance_issues(performance_analyses)
        error_pattern_issues = await self._detect_error_pattern_issues(error_analyses)
        integration_issues = await self._detect_integration_issues(test_results)
        security_issues = await self._detect_security_issues(test_results)
        
        # Combine all issues
        all_issues = (functionality_issues + performance_issues + 
                     error_pattern_issues + integration_issues + security_issues)
        
        # Deduplicate and merge related issues
        deduplicated_issues = await self._deduplicate_issues(all_issues)
        
        # Calculate priority scores for each issue
        for issue in deduplicated_issues:
            priority_score = await self._calculate_priority_score(issue)
            self.priority_scores[issue.id] = priority_score
            
            # Update issue with calculated priority
            issue.fix_priority = int(priority_score.total_score)
        
        # Sort issues by priority
        self.identified_issues = sorted(deduplicated_issues, 
                                      key=lambda x: self.priority_scores[x.id].total_score, 
                                      reverse=True)
        
        self.logger.info(f"Issue analysis complete. Identified {len(self.identified_issues)} issues")
        return self.identified_issues
    
    async def get_critical_issues(self, max_count: Optional[int] = None) -> List[Issue]:
        """Get critical issues that require immediate attention."""
        critical_issues = [
            issue for issue in self.identified_issues 
            if issue.severity == IssueSeverity.CRITICAL
        ]
        
        if max_count:
            critical_issues = critical_issues[:max_count]
        
        return critical_issues
    
    async def get_priority_breakdown(self) -> Dict[str, Any]:
        """Get breakdown of issues by priority and category."""
        if not self.identified_issues:
            return {}
        
        # Count by severity
        severity_counts = Counter(issue.severity.value for issue in self.identified_issues)
        
        # Count by category
        category_counts = Counter(issue.category.value for issue in self.identified_issues)
        
        # Calculate average priority scores
        total_score = sum(score.total_score for score in self.priority_scores.values())
        avg_score = total_score / len(self.priority_scores) if self.priority_scores else 0
        
        # Get top priority issues
        top_issues = self.identified_issues[:5]  # Top 5 by priority
        
        return {
            'total_issues': len(self.identified_issues),
            'severity_distribution': dict(severity_counts),
            'category_distribution': dict(category_counts),
            'average_priority_score': avg_score,
            'top_priority_issues': [
                {
                    'id': issue.id,
                    'title': issue.title,
                    'severity': issue.severity.value,
                    'category': issue.category.value,
                    'priority_score': self.priority_scores[issue.id].total_score
                }
                for issue in top_issues
            ]
        }
    
    async def generate_action_items(self, issues: Optional[List[Issue]] = None) -> List[ActionItem]:
        """Generate actionable items from identified issues."""
        if issues is None:
            issues = self.identified_issues
        
        action_items = []
        
        for issue in issues:
            # Generate action items based on issue category and severity
            items = await self._generate_issue_action_items(issue)
            action_items.extend(items)
        
        # Sort action items by priority
        action_items.sort(key=lambda x: self._get_priority_order(x.priority), reverse=True)
        
        return action_items
    
    async def generate_user_actions(self, issues: Optional[List[Issue]] = None) -> List[UserAction]:
        """Generate user actions required to address issues."""
        if issues is None:
            issues = self.identified_issues
        
        user_actions = []
        
        for issue in issues:
            # Generate user actions based on issue type
            actions = await self._generate_issue_user_actions(issue)
            user_actions.extend(actions)
        
        # Sort by urgency
        user_actions.sort(key=lambda x: self._get_urgency_order(x.urgency), reverse=True)
        
        return user_actions
    
    async def _detect_functionality_issues(self, test_results: List[TestResult], 
                                         suite_results: List[TestSuiteResult]) -> List[Issue]:
        """Detect functionality-related issues from test results."""
        issues = []
        
        # Analyze failed tests
        failed_tests = [t for t in test_results if t.status == TestStatus.FAILED]
        error_tests = [t for t in test_results if t.status == TestStatus.ERROR]
        
        # Group failures by component
        component_failures = defaultdict(list)
        for test in failed_tests + error_tests:
            component = self._extract_component_from_test_name(test.test_name)
            component_failures[component].append(test)
        
        # Create issues for components with high failure rates
        for component, failures in component_failures.items():
            total_component_tests = len([t for t in test_results 
                                       if self._extract_component_from_test_name(t.test_name) == component])
            
            if total_component_tests == 0:
                continue
                
            failure_rate = len(failures) / total_component_tests
            
            if failure_rate >= self.detection_thresholds['critical_error_rate']:
                severity = IssueSeverity.CRITICAL
            elif failure_rate >= self.detection_thresholds['high_error_rate']:
                severity = IssueSeverity.HIGH
            else:
                continue  # Not significant enough
            
            # Create issue
            issue = Issue(
                id=f"functionality_{component}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                severity=severity,
                category=IssueCategory.FUNCTIONALITY,
                title=f"High failure rate in {component} component",
                description=f"Component {component} has {failure_rate:.1%} test failure rate ({len(failures)}/{total_component_tests} tests failed)",
                affected_components=[component],
                reproduction_steps=self._generate_reproduction_steps(failures[:3]),  # Top 3 failures
                expected_behavior=f"All {component} tests should pass",
                actual_behavior=f"{len(failures)} out of {total_component_tests} tests are failing",
                fix_priority=0,  # Will be calculated later
                estimated_effort=self._estimate_fix_effort(severity, len(failures))
            )
            
            issues.append(issue)
            
            # Create issue context
            self.issue_contexts[issue.id] = IssueContext(
                affected_users=self._estimate_affected_users(component),
                business_impact=self._assess_business_impact(component, severity),
                component_criticality=self._get_component_criticality(component),
                frequency=len(failures),
                trend="STABLE",  # Would need historical data for trend analysis
                related_issues=[],
                external_dependencies=self._identify_external_dependencies(component)
            )
        
        return issues
    
    async def _detect_performance_issues(self, performance_analyses: List[PerformanceAnalysis]) -> List[Issue]:
        """Detect performance-related issues."""
        issues = []
        
        for analysis in performance_analyses:
            performance_issues_found = []
            
            # Check response time issues
            if analysis.avg_response_time > self.detection_thresholds['critical_response_time']:
                performance_issues_found.append(f"Critical average response time: {analysis.avg_response_time:.2f}s")
                severity = IssueSeverity.CRITICAL
            elif analysis.avg_response_time > self.detection_thresholds['high_response_time']:
                performance_issues_found.append(f"High average response time: {analysis.avg_response_time:.2f}s")
                severity = IssueSeverity.HIGH
            else:
                severity = IssueSeverity.MEDIUM
            
            # Check P95 response time
            if analysis.p95_response_time > self.detection_thresholds['critical_response_time'] * 1.5:
                performance_issues_found.append(f"Critical P95 response time: {analysis.p95_response_time:.2f}s")
                severity = max(severity, IssueSeverity.HIGH, key=lambda x: x.value)
            
            # Check error rate
            if analysis.error_rate > self.detection_thresholds['critical_error_rate']:
                performance_issues_found.append(f"Critical error rate: {analysis.error_rate:.1%}")
                severity = IssueSeverity.CRITICAL
            elif analysis.error_rate > self.detection_thresholds['high_error_rate']:
                performance_issues_found.append(f"High error rate: {analysis.error_rate:.1%}")
                severity = max(severity, IssueSeverity.HIGH, key=lambda x: x.value)
            
            # Create issue if performance problems found
            if performance_issues_found:
                issue = Issue(
                    id=f"performance_{analysis.component_name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    severity=severity,
                    category=IssueCategory.PERFORMANCE,
                    title=f"Performance issues in {analysis.component_name}",
                    description=f"Performance degradation detected: {'; '.join(performance_issues_found)}",
                    affected_components=[analysis.component_name],
                    reproduction_steps=[
                        f"Execute performance tests for {analysis.component_name}",
                        "Monitor response times and error rates",
                        "Compare against performance baselines"
                    ],
                    expected_behavior=f"Response times should be under {self.detection_thresholds['high_response_time']}s with error rate under {self.detection_thresholds['high_error_rate']:.1%}",
                    actual_behavior=f"Average response time: {analysis.avg_response_time:.2f}s, Error rate: {analysis.error_rate:.1%}",
                    fix_priority=0,
                    estimated_effort=self._estimate_performance_fix_effort(analysis)
                )
                
                issues.append(issue)
                
                # Create issue context
                self.issue_contexts[issue.id] = IssueContext(
                    affected_users=self._estimate_affected_users(analysis.component_name),
                    business_impact=self._assess_performance_business_impact(analysis),
                    component_criticality=self._get_component_criticality(analysis.component_name),
                    frequency=1,  # Performance issues are typically ongoing
                    trend="STABLE",
                    related_issues=[],
                    external_dependencies=self._identify_external_dependencies(analysis.component_name)
                )
        
        return issues
    
    async def _detect_error_pattern_issues(self, error_analyses: List[ErrorAnalysis]) -> List[Issue]:
        """Detect issues from error pattern analysis."""
        issues = []
        
        for error_analysis in error_analyses:
            # Only create issues for frequent or critical errors
            if error_analysis.frequency < self.detection_thresholds['frequent_error_threshold']:
                continue
            
            # Determine severity based on error category and frequency
            severity = self._determine_error_severity(error_analysis)
            
            issue = Issue(
                id=f"error_pattern_{hash(error_analysis.error_message) % 10000}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                severity=severity,
                category=self._map_error_category_to_issue_category(error_analysis.error_category),
                title=f"Frequent {error_analysis.error_category.value.replace('_', ' ')}: {error_analysis.error_message[:50]}...",
                description=f"Error pattern detected {error_analysis.frequency} times between {error_analysis.first_occurrence} and {error_analysis.last_occurrence}",
                affected_components=list(set(self._extract_component_from_test_name(test) for test in error_analysis.affected_tests)),
                reproduction_steps=error_analysis.suggested_fixes[:3],  # Use suggested fixes as reproduction steps
                expected_behavior="No errors should occur during normal operation",
                actual_behavior=f"Error occurs frequently: {error_analysis.error_message}",
                fix_priority=0,
                estimated_effort=self._estimate_error_fix_effort(error_analysis)
            )
            
            issues.append(issue)
            
            # Create issue context
            affected_components = list(set(self._extract_component_from_test_name(test) for test in error_analysis.affected_tests))
            primary_component = affected_components[0] if affected_components else "unknown"
            
            self.issue_contexts[issue.id] = IssueContext(
                affected_users=self._estimate_affected_users(primary_component),
                business_impact=self._assess_error_business_impact(error_analysis),
                component_criticality=self._get_component_criticality(primary_component),
                frequency=error_analysis.frequency,
                trend=self._analyze_error_trend(error_analysis),
                related_issues=[],
                external_dependencies=[]
            )
        
        return issues
    
    async def _detect_integration_issues(self, test_results: List[TestResult]) -> List[Issue]:
        """Detect integration-related issues."""
        issues = []
        
        # Find integration tests
        integration_tests = [t for t in test_results if 'integration' in t.test_name.lower() or 
                           'webhook' in t.test_name.lower() or 'api' in t.test_name.lower()]
        
        # Group by integration type
        integration_failures = defaultdict(list)
        for test in integration_tests:
            if test.status in [TestStatus.FAILED, TestStatus.ERROR]:
                integration_type = self._extract_integration_type(test.test_name)
                integration_failures[integration_type].append(test)
        
        # Create issues for problematic integrations
        for integration_type, failures in integration_failures.items():
            if len(failures) >= 2:  # At least 2 failures to be considered an issue
                issue = Issue(
                    id=f"integration_{integration_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    severity=IssueSeverity.HIGH if len(failures) >= 5 else IssueSeverity.MEDIUM,
                    category=IssueCategory.FUNCTIONALITY,
                    title=f"Integration issues with {integration_type}",
                    description=f"Multiple integration test failures detected for {integration_type} ({len(failures)} failures)",
                    affected_components=[integration_type],
                    reproduction_steps=self._generate_integration_reproduction_steps(integration_type, failures),
                    expected_behavior=f"All {integration_type} integration tests should pass",
                    actual_behavior=f"{len(failures)} integration tests are failing",
                    fix_priority=0,
                    estimated_effort="2-5 days"
                )
                
                issues.append(issue)
                
                self.issue_contexts[issue.id] = IssueContext(
                    affected_users=self._estimate_integration_affected_users(integration_type),
                    business_impact=self._assess_integration_business_impact(integration_type),
                    component_criticality=ComponentCriticality.IMPORTANT,
                    frequency=len(failures),
                    trend="STABLE",
                    related_issues=[],
                    external_dependencies=[integration_type]
                )
        
        return issues
    
    async def _detect_security_issues(self, test_results: List[TestResult]) -> List[Issue]:
        """Detect security-related issues."""
        issues = []
        
        # Find security-related test failures
        security_tests = [t for t in test_results if any(keyword in t.test_name.lower() 
                         for keyword in ['auth', 'security', 'permission', 'access', 'token', 'oauth'])]
        
        security_failures = [t for t in security_tests if t.status in [TestStatus.FAILED, TestStatus.ERROR]]
        
        if security_failures:
            # Group by security area
            security_areas = defaultdict(list)
            for test in security_failures:
                area = self._extract_security_area(test.test_name)
                security_areas[area].append(test)
            
            for area, failures in security_areas.items():
                issue = Issue(
                    id=f"security_{area}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                    severity=IssueSeverity.CRITICAL,  # Security issues are always critical
                    category=IssueCategory.SECURITY,
                    title=f"Security vulnerabilities in {area}",
                    description=f"Security test failures detected in {area} ({len(failures)} failures)",
                    affected_components=[area],
                    reproduction_steps=self._generate_security_reproduction_steps(area, failures),
                    expected_behavior=f"All {area} security tests should pass",
                    actual_behavior=f"{len(failures)} security tests are failing",
                    fix_priority=0,
                    estimated_effort="1-3 days"
                )
                
                issues.append(issue)
                
                self.issue_contexts[issue.id] = IssueContext(
                    affected_users=1000,  # Security issues potentially affect all users
                    business_impact="Critical security vulnerability",
                    component_criticality=ComponentCriticality.CORE,
                    frequency=len(failures),
                    trend="STABLE",
                    related_issues=[],
                    external_dependencies=[]
                )
        
        return issues
    
    async def _deduplicate_issues(self, issues: List[Issue]) -> List[Issue]:
        """Deduplicate and merge related issues."""
        if not issues:
            return []
        
        # Simple deduplication based on title similarity and affected components
        deduplicated = []
        processed_signatures = set()
        
        for issue in issues:
            # Create signature for deduplication
            signature = f"{issue.category.value}_{'-'.join(sorted(issue.affected_components))}"
            
            if signature not in processed_signatures:
                deduplicated.append(issue)
                processed_signatures.add(signature)
            else:
                # Find existing issue and potentially merge
                existing_issue = next(i for i in deduplicated 
                                    if f"{i.category.value}_{'-'.join(sorted(i.affected_components))}" == signature)
                
                # Merge if severity is higher
                if issue.severity.value > existing_issue.severity.value:
                    existing_issue.severity = issue.severity
                    existing_issue.description += f" | {issue.description}"
        
        return deduplicated
    
    async def _calculate_priority_score(self, issue: Issue) -> PriorityScore:
        """Calculate comprehensive priority score for an issue."""
        context = self.issue_contexts.get(issue.id)
        if not context:
            # Create default context
            context = IssueContext(
                affected_users=1,
                business_impact="Unknown",
                component_criticality=ComponentCriticality.SUPPORTING,
                frequency=1,
                trend="STABLE",
                related_issues=[],
                external_dependencies=[]
            )
        
        # Calculate individual scores (0-100 scale)
        severity_score = self._calculate_severity_score(issue.severity)
        impact_score = self._calculate_impact_score(context)
        frequency_score = self._calculate_frequency_score(context.frequency)
        trend_score = self._calculate_trend_score(context.trend)
        component_score = self._calculate_component_score(context.component_criticality)
        
        # Calculate weighted total score
        total_score = (
            severity_score * self.scoring_weights['severity'] +
            impact_score * self.scoring_weights['impact'] +
            frequency_score * self.scoring_weights['frequency'] +
            trend_score * self.scoring_weights['trend'] +
            component_score * self.scoring_weights['component']
        )
        
        # Determine priority level
        if total_score >= 80:
            priority_level = Priority.HIGH
        elif total_score >= 50:
            priority_level = Priority.MEDIUM
        else:
            priority_level = Priority.LOW
        
        return PriorityScore(
            severity_score=severity_score,
            impact_score=impact_score,
            frequency_score=frequency_score,
            trend_score=trend_score,
            component_score=component_score,
            total_score=total_score,
            priority_level=priority_level
        )
    
    def _calculate_severity_score(self, severity: IssueSeverity) -> float:
        """Calculate score based on issue severity."""
        severity_scores = {
            IssueSeverity.CRITICAL: 100.0,
            IssueSeverity.HIGH: 75.0,
            IssueSeverity.MEDIUM: 50.0,
            IssueSeverity.LOW: 25.0
        }
        return severity_scores.get(severity, 25.0)
    
    def _calculate_impact_score(self, context: IssueContext) -> float:
        """Calculate score based on business impact."""
        # Base score on affected users (logarithmic scale)
        user_score = min(100.0, math.log10(max(1, context.affected_users)) * 20)
        
        # Adjust based on business impact description
        impact_multipliers = {
            'critical': 1.0,
            'revenue': 0.9,
            'user experience': 0.8,
            'operational': 0.7,
            'minor': 0.5
        }
        
        multiplier = 0.7  # default
        for keyword, mult in impact_multipliers.items():
            if keyword in context.business_impact.lower():
                multiplier = mult
                break
        
        return user_score * multiplier
    
    def _calculate_frequency_score(self, frequency: int) -> float:
        """Calculate score based on issue frequency."""
        # Logarithmic scale for frequency
        return min(100.0, math.log10(max(1, frequency)) * 30)
    
    def _calculate_trend_score(self, trend: str) -> float:
        """Calculate score based on issue trend."""
        trend_scores = {
            'INCREASING': 100.0,
            'STABLE': 50.0,
            'DECREASING': 25.0
        }
        return trend_scores.get(trend, 50.0)
    
    def _calculate_component_score(self, criticality: ComponentCriticality) -> float:
        """Calculate score based on component criticality."""
        criticality_scores = {
            ComponentCriticality.CORE: 100.0,
            ComponentCriticality.IMPORTANT: 75.0,
            ComponentCriticality.SUPPORTING: 50.0,
            ComponentCriticality.OPTIONAL: 25.0
        }
        return criticality_scores.get(criticality, 50.0)
    
    # Helper methods for issue generation
    def _extract_component_from_test_name(self, test_name: str) -> str:
        """Extract component name from test name."""
        # Common patterns in test names
        if 'auth' in test_name.lower():
            return 'authentication'
        elif 'billing' in test_name.lower() or 'stripe' in test_name.lower():
            return 'billing'
        elif 'crm' in test_name.lower():
            return 'crm'
        elif 'kyb' in test_name.lower():
            return 'kyb'
        elif 'calendar' in test_name.lower():
            return 'calendar'
        elif 'knowledge' in test_name.lower():
            return 'knowledge'
        elif 'telegram' in test_name.lower():
            return 'telegram'
        elif 'signal' in test_name.lower():
            return 'signal'
        elif 'api' in test_name.lower():
            return 'api'
        else:
            return 'unknown'
    
    def _get_component_criticality(self, component: str) -> ComponentCriticality:
        """Get criticality level for a component."""
        return self.component_criticality_map.get(component.lower(), ComponentCriticality.SUPPORTING)
    
    def _estimate_affected_users(self, component: str) -> int:
        """Estimate number of users affected by component issues."""
        # Rough estimates based on component importance
        user_estimates = {
            'authentication': 1000,  # All users
            'billing': 800,  # Most paying users
            'crm': 600,  # Business users
            'kyb': 400,  # Compliance users
            'calendar': 300,  # Calendar users
            'knowledge': 200,  # Knowledge users
            'telegram': 150,  # Telegram users
            'signal': 100,  # Signal users
            'api': 500,  # API users
        }
        return user_estimates.get(component.lower(), 50)
    
    def _assess_business_impact(self, component: str, severity: IssueSeverity) -> str:
        """Assess business impact of component issues."""
        if severity == IssueSeverity.CRITICAL:
            if component in ['authentication', 'billing']:
                return "Critical business impact - service unavailable"
            else:
                return "High business impact - major feature unavailable"
        elif severity == IssueSeverity.HIGH:
            return "Medium business impact - degraded user experience"
        else:
            return "Low business impact - minor functionality affected"
    
    def _estimate_fix_effort(self, severity: IssueSeverity, failure_count: int) -> str:
        """Estimate effort required to fix issues."""
        if severity == IssueSeverity.CRITICAL:
            return "1-3 days"
        elif severity == IssueSeverity.HIGH:
            if failure_count > 10:
                return "3-7 days"
            else:
                return "1-3 days"
        else:
            return "1-2 days"
    
    # Additional helper methods would continue here...
    # (Implementation continues with remaining helper methods)
    
    async def _generate_issue_action_items(self, issue: Issue) -> List[ActionItem]:
        """Generate action items for an issue."""
        action_items = []
        
        # Create investigation action item
        investigation_item = ActionItem(
            id=f"investigate_{issue.id}",
            title=f"Investigate {issue.title}",
            description=f"Analyze root cause of {issue.category.value} issue in {', '.join(issue.affected_components)}",
            priority=Priority.HIGH if issue.severity in [IssueSeverity.CRITICAL, IssueSeverity.HIGH] else Priority.MEDIUM,
            estimated_time="4-8 hours",
            assigned_to="development_team",
            dependencies=[],
            acceptance_criteria=[
                "Root cause identified and documented",
                "Impact assessment completed",
                "Fix approach determined"
            ]
        )
        action_items.append(investigation_item)
        
        # Create fix action item
        fix_item = ActionItem(
            id=f"fix_{issue.id}",
            title=f"Fix {issue.title}",
            description=f"Implement fix for {issue.description}",
            priority=Priority.HIGH if issue.severity == IssueSeverity.CRITICAL else Priority.MEDIUM,
            estimated_time=issue.estimated_effort,
            assigned_to="development_team",
            dependencies=[investigation_item.id],
            acceptance_criteria=[
                "Issue resolved and verified",
                "Tests passing",
                "No regression introduced"
            ]
        )
        action_items.append(fix_item)
        
        return action_items
    
    async def _generate_issue_user_actions(self, issue: Issue) -> List[UserAction]:
        """Generate user actions for an issue."""
        user_actions = []
        
        if issue.severity == IssueSeverity.CRITICAL:
            urgency = Urgency.IMMEDIATE
        elif issue.severity == IssueSeverity.HIGH:
            urgency = Urgency.SOON
        else:
            urgency = Urgency.WHEN_CONVENIENT
        
        # Create monitoring action
        monitoring_action = UserAction(
            id=f"monitor_{issue.id}",
            title=f"Monitor {issue.title}",
            description=f"Monitor the impact of {issue.title} on system operations",
            urgency=urgency,
            instructions=[
                f"Check {', '.join(issue.affected_components)} component status regularly",
                "Monitor error rates and performance metrics",
                "Report any escalation in severity"
            ],
            expected_outcome="Early detection of issue escalation"
        )
        user_actions.append(monitoring_action)
        
        return user_actions
    
    def _get_priority_order(self, priority: Priority) -> int:
        """Get numeric order for priority sorting."""
        order_map = {Priority.HIGH: 3, Priority.MEDIUM: 2, Priority.LOW: 1}
        return order_map.get(priority, 1)
    
    def _get_urgency_order(self, urgency: Urgency) -> int:
        """Get numeric order for urgency sorting."""
        order_map = {Urgency.IMMEDIATE: 3, Urgency.SOON: 2, Urgency.WHEN_CONVENIENT: 1}
        return order_map.get(urgency, 1)
    
    # Placeholder implementations for remaining helper methods
    def _estimate_performance_fix_effort(self, analysis: PerformanceAnalysis) -> str:
        return "2-5 days"
    
    def _assess_performance_business_impact(self, analysis: PerformanceAnalysis) -> str:
        return "Performance degradation affecting user experience"
    
    def _determine_error_severity(self, error_analysis: ErrorAnalysis) -> IssueSeverity:
        if error_analysis.frequency >= 50:
            return IssueSeverity.CRITICAL
        elif error_analysis.frequency >= 20:
            return IssueSeverity.HIGH
        else:
            return IssueSeverity.MEDIUM
    
    def _map_error_category_to_issue_category(self, error_category) -> IssueCategory:
        return IssueCategory.FUNCTIONALITY  # Simplified mapping
    
    def _estimate_error_fix_effort(self, error_analysis: ErrorAnalysis) -> str:
        return "1-3 days"
    
    def _assess_error_business_impact(self, error_analysis: ErrorAnalysis) -> str:
        return "Error affecting system reliability"
    
    def _analyze_error_trend(self, error_analysis: ErrorAnalysis) -> str:
        return "STABLE"  # Would need historical data for proper trend analysis
    
    def _identify_external_dependencies(self, component: str) -> List[str]:
        return []  # Simplified implementation
    
    def _extract_integration_type(self, test_name: str) -> str:
        if 'telegram' in test_name.lower():
            return 'telegram'
        elif 'stripe' in test_name.lower():
            return 'stripe'
        elif 'google' in test_name.lower():
            return 'google'
        else:
            return 'unknown'
    
    def _generate_reproduction_steps(self, failures: List[TestResult]) -> List[str]:
        return [f"Run test: {test.test_name}" for test in failures[:3]]
    
    def _generate_integration_reproduction_steps(self, integration_type: str, failures: List[TestResult]) -> List[str]:
        return [f"Test {integration_type} integration", "Check external service connectivity"]
    
    def _estimate_integration_affected_users(self, integration_type: str) -> int:
        return 100  # Simplified estimate
    
    def _assess_integration_business_impact(self, integration_type: str) -> str:
        return f"Integration with {integration_type} not working properly"
    
    def _extract_security_area(self, test_name: str) -> str:
        if 'auth' in test_name.lower():
            return 'authentication'
        elif 'oauth' in test_name.lower():
            return 'oauth'
        else:
            return 'security'
    
    def _generate_security_reproduction_steps(self, area: str, failures: List[TestResult]) -> List[str]:
        return [f"Test {area} security", "Verify access controls"]