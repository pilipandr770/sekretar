"""
Improvement Plan and User Action Generation System

Implements automated improvement plan generation, user action item identification,
and timeline and effort estimation for comprehensive testing framework.
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from tests.infrastructure.models import (
    Issue, IssueSeverity, IssueCategory, ActionItem, Priority, 
    UserAction, Urgency, ComprehensiveReport
)


class PlanType(Enum):
    """Types of improvement plans."""
    IMMEDIATE_FIXES = "immediate_fixes"
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    PREVENTIVE = "preventive"


class ResourceType(Enum):
    """Types of resources needed for improvements."""
    DEVELOPER_TIME = "developer_time"
    INFRASTRUCTURE = "infrastructure"
    EXTERNAL_SERVICE = "external_service"
    TESTING_TIME = "testing_time"
    DOCUMENTATION = "documentation"


@dataclass
class ResourceRequirement:
    """Resource requirement for an improvement item."""
    resource_type: ResourceType
    quantity: float
    unit: str  # hours, days, instances, etc.
    cost_estimate: Optional[float] = None
    availability: str = "available"  # available, limited, unavailable


@dataclass
class Timeline:
    """Timeline for improvement implementation."""
    start_date: datetime
    end_date: datetime
    milestones: List[Dict[str, Any]]
    dependencies: List[str]
    critical_path: bool = False


@dataclass
class ImprovementPlan:
    """Comprehensive improvement plan."""
    id: str
    title: str
    description: str
    plan_type: PlanType
    priority: Priority
    issues_addressed: List[str]  # Issue IDs
    action_items: List[ActionItem]
    user_actions: List[UserAction]
    resource_requirements: List[ResourceRequirement]
    timeline: Timeline
    success_metrics: List[str]
    risk_assessment: Dict[str, Any]
    estimated_impact: str


@dataclass
class ImplementationPhase:
    """Implementation phase for improvement plans."""
    phase_name: str
    description: str
    duration_days: int
    prerequisites: List[str]
    deliverables: List[str]
    success_criteria: List[str]
    risks: List[str]


class ImprovementPlanner:
    """
    Advanced improvement plan and user action generation system.
    
    Analyzes identified issues and generates comprehensive improvement plans
    with timelines, resource requirements, and user actions.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize improvement planner."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Planning configuration
        self.planning_config = {
            'max_parallel_critical_fixes': self.config.get('max_parallel_critical_fixes', 3),
            'developer_hours_per_day': self.config.get('developer_hours_per_day', 6),
            'testing_hours_per_day': self.config.get('testing_hours_per_day', 4),
            'buffer_percentage': self.config.get('buffer_percentage', 0.20),  # 20% buffer
            'max_plan_duration_days': self.config.get('max_plan_duration_days', 90)
        }
        
        # Resource capacity
        self.resource_capacity = {
            ResourceType.DEVELOPER_TIME: self.config.get('developer_capacity_hours_per_day', 24),  # Team capacity
            ResourceType.TESTING_TIME: self.config.get('testing_capacity_hours_per_day', 8),
            ResourceType.INFRASTRUCTURE: self.config.get('infrastructure_capacity', 10),
            ResourceType.DOCUMENTATION: self.config.get('documentation_capacity_hours_per_day', 4)
        }
        
        # Effort estimation models
        self.effort_models = {
            IssueCategory.FUNCTIONALITY: {
                IssueSeverity.CRITICAL: {'min_hours': 16, 'max_hours': 40, 'complexity_factor': 1.5},
                IssueSeverity.HIGH: {'min_hours': 8, 'max_hours': 24, 'complexity_factor': 1.3},
                IssueSeverity.MEDIUM: {'min_hours': 4, 'max_hours': 16, 'complexity_factor': 1.2},
                IssueSeverity.LOW: {'min_hours': 2, 'max_hours': 8, 'complexity_factor': 1.1}
            },
            IssueCategory.PERFORMANCE: {
                IssueSeverity.CRITICAL: {'min_hours': 24, 'max_hours': 60, 'complexity_factor': 1.8},
                IssueSeverity.HIGH: {'min_hours': 12, 'max_hours': 32, 'complexity_factor': 1.5},
                IssueSeverity.MEDIUM: {'min_hours': 6, 'max_hours': 20, 'complexity_factor': 1.3},
                IssueSeverity.LOW: {'min_hours': 3, 'max_hours': 12, 'complexity_factor': 1.2}
            },
            IssueCategory.SECURITY: {
                IssueSeverity.CRITICAL: {'min_hours': 8, 'max_hours': 24, 'complexity_factor': 1.2},
                IssueSeverity.HIGH: {'min_hours': 4, 'max_hours': 16, 'complexity_factor': 1.1},
                IssueSeverity.MEDIUM: {'min_hours': 2, 'max_hours': 8, 'complexity_factor': 1.0},
                IssueSeverity.LOW: {'min_hours': 1, 'max_hours': 4, 'complexity_factor': 1.0}
            },
            IssueCategory.USABILITY: {
                IssueSeverity.CRITICAL: {'min_hours': 12, 'max_hours': 30, 'complexity_factor': 1.3},
                IssueSeverity.HIGH: {'min_hours': 6, 'max_hours': 18, 'complexity_factor': 1.2},
                IssueSeverity.MEDIUM: {'min_hours': 3, 'max_hours': 12, 'complexity_factor': 1.1},
                IssueSeverity.LOW: {'min_hours': 1, 'max_hours': 6, 'complexity_factor': 1.0}
            }
        }
        
        # Generated plans
        self.improvement_plans: List[ImprovementPlan] = []
        self.user_actions: List[UserAction] = []
        self.resource_allocation: Dict[ResourceType, float] = defaultdict(float)
    
    async def generate_comprehensive_improvement_plan(self, issues: List[Issue]) -> Dict[str, Any]:
        """
        Generate comprehensive improvement plan from identified issues.
        
        Args:
            issues: List of identified issues
            
        Returns:
            Dictionary containing improvement plans, user actions, and implementation timeline
        """
        self.logger.info(f"Generating comprehensive improvement plan for {len(issues)} issues")
        
        # Clear previous plans
        self.improvement_plans.clear()
        self.user_actions.clear()
        self.resource_allocation.clear()
        
        # Categorize issues by priority and type
        categorized_issues = self._categorize_issues(issues)
        
        # Generate different types of improvement plans
        immediate_plan = await self._generate_immediate_fixes_plan(categorized_issues['critical'])
        short_term_plan = await self._generate_short_term_plan(categorized_issues['high'])
        long_term_plan = await self._generate_long_term_plan(categorized_issues['medium'] + categorized_issues['low'])
        preventive_plan = await self._generate_preventive_plan(issues)
        
        # Add plans to collection
        if immediate_plan:
            self.improvement_plans.append(immediate_plan)
        if short_term_plan:
            self.improvement_plans.append(short_term_plan)
        if long_term_plan:
            self.improvement_plans.append(long_term_plan)
        if preventive_plan:
            self.improvement_plans.append(preventive_plan)
        
        # Generate user actions
        self.user_actions = await self._generate_comprehensive_user_actions(issues)
        
        # Create implementation timeline
        implementation_timeline = await self._create_implementation_timeline()
        
        # Calculate resource requirements
        resource_summary = await self._calculate_resource_summary()
        
        # Generate success metrics
        success_metrics = await self._generate_success_metrics(issues)
        
        # Create comprehensive plan summary
        plan_summary = {
            'total_issues': len(issues),
            'improvement_plans': len(self.improvement_plans),
            'total_action_items': sum(len(plan.action_items) for plan in self.improvement_plans),
            'total_user_actions': len(self.user_actions),
            'estimated_duration_days': implementation_timeline.get('total_duration_days', 0),
            'resource_requirements': resource_summary,
            'success_metrics': success_metrics,
            'implementation_phases': implementation_timeline.get('phases', [])
        }
        
        self.logger.info("Comprehensive improvement plan generation complete")
        
        return {
            'improvement_plans': self.improvement_plans,
            'user_actions': self.user_actions,
            'implementation_timeline': implementation_timeline,
            'resource_summary': resource_summary,
            'plan_summary': plan_summary,
            'success_metrics': success_metrics
        } 
   
    async def generate_executive_summary(self, issues: List[Issue]) -> Dict[str, Any]:
        """Generate executive summary of improvement recommendations."""
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        high_issues = [i for i in issues if i.severity == IssueSeverity.HIGH]
        
        # Calculate impact metrics
        total_estimated_hours = sum(self._estimate_fix_hours(issue) for issue in issues)
        total_estimated_days = total_estimated_hours / self.planning_config['developer_hours_per_day']
        
        # Identify top priorities
        top_priorities = sorted(issues, key=lambda x: x.fix_priority, reverse=True)[:5]
        
        # Calculate business impact
        business_impact = self._assess_overall_business_impact(issues)
        
        return {
            'executive_summary': {
                'total_issues_identified': len(issues),
                'critical_issues': len(critical_issues),
                'high_priority_issues': len(high_issues),
                'estimated_fix_duration_days': int(total_estimated_days),
                'business_impact_assessment': business_impact,
                'immediate_action_required': len(critical_issues) > 0,
                'top_priority_issues': [
                    {
                        'title': issue.title,
                        'severity': issue.severity.value,
                        'affected_components': issue.affected_components,
                        'estimated_effort': issue.estimated_effort
                    }
                    for issue in top_priorities
                ]
            },
            'recommendations': {
                'immediate_actions': await self._generate_immediate_recommendations(critical_issues),
                'short_term_actions': await self._generate_short_term_recommendations(high_issues),
                'resource_needs': await self._identify_resource_needs(issues),
                'risk_mitigation': await self._identify_risk_mitigation_strategies(issues)
            }
        }
    
    def _categorize_issues(self, issues: List[Issue]) -> Dict[str, List[Issue]]:
        """Categorize issues by severity for planning purposes."""
        categorized = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': []
        }
        
        for issue in issues:
            categorized[issue.severity.value].append(issue)
        
        return categorized
    
    async def _generate_immediate_fixes_plan(self, critical_issues: List[Issue]) -> Optional[ImprovementPlan]:
        """Generate plan for immediate critical fixes."""
        if not critical_issues:
            return None
        
        # Limit to most critical issues that can be handled in parallel
        max_parallel = self.planning_config['max_parallel_critical_fixes']
        priority_issues = sorted(critical_issues, key=lambda x: x.fix_priority, reverse=True)[:max_parallel]
        
        # Generate action items
        action_items = []
        user_actions = []
        
        for issue in priority_issues:
            # Create immediate fix action
            fix_action = ActionItem(
                id=f"immediate_fix_{issue.id}",
                title=f"URGENT: Fix {issue.title}",
                description=f"Immediate fix required for critical issue: {issue.description}",
                priority=Priority.HIGH,
                estimated_time=issue.estimated_effort,
                assigned_to="senior_developer",
                dependencies=[],
                acceptance_criteria=[
                    "Issue completely resolved",
                    "No regression introduced",
                    "Monitoring confirms fix effectiveness",
                    "Documentation updated"
                ]
            )
            action_items.append(fix_action)
            
            # Create monitoring user action
            monitor_action = UserAction(
                id=f"monitor_critical_{issue.id}",
                title=f"Monitor critical fix: {issue.title}",
                description=f"Closely monitor the resolution of critical issue",
                urgency=Urgency.IMMEDIATE,
                instructions=[
                    "Check system status every 30 minutes",
                    "Monitor error rates and performance metrics",
                    "Escalate immediately if issue persists",
                    "Communicate status to stakeholders"
                ],
                expected_outcome="Issue resolved within 24 hours"
            )
            user_actions.append(monitor_action)
        
        # Calculate resource requirements
        total_dev_hours = sum(self._estimate_fix_hours(issue) for issue in priority_issues)
        resource_requirements = [
            ResourceRequirement(
                resource_type=ResourceType.DEVELOPER_TIME,
                quantity=total_dev_hours,
                unit="hours",
                availability="immediate"
            ),
            ResourceRequirement(
                resource_type=ResourceType.TESTING_TIME,
                quantity=total_dev_hours * 0.5,  # 50% of dev time for testing
                unit="hours",
                availability="immediate"
            )
        ]
        
        # Create timeline
        max_duration_hours = max(self._estimate_fix_hours(issue) for issue in priority_issues)
        timeline = Timeline(
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(hours=max_duration_hours * 1.2),  # 20% buffer
            milestones=[
                {
                    'name': 'Critical fixes deployed',
                    'date': datetime.utcnow() + timedelta(hours=max_duration_hours),
                    'description': 'All critical issues resolved and deployed'
                }
            ],
            dependencies=[],
            critical_path=True
        )
        
        return ImprovementPlan(
            id=f"immediate_fixes_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Immediate Critical Fixes",
            description=f"Urgent resolution of {len(priority_issues)} critical issues requiring immediate attention",
            plan_type=PlanType.IMMEDIATE_FIXES,
            priority=Priority.HIGH,
            issues_addressed=[issue.id for issue in priority_issues],
            action_items=action_items,
            user_actions=user_actions,
            resource_requirements=resource_requirements,
            timeline=timeline,
            success_metrics=[
                "All critical issues resolved within 24 hours",
                "System stability restored",
                "No new critical issues introduced",
                "User impact minimized"
            ],
            risk_assessment={
                'high_risks': ['Potential for introducing regressions', 'Resource availability'],
                'mitigation_strategies': ['Thorough testing', 'Rollback plan ready', 'Senior developer assignment']
            },
            estimated_impact="Immediate restoration of system stability and user confidence"
        ) 
   
    async def _generate_short_term_plan(self, high_issues: List[Issue]) -> Optional[ImprovementPlan]:
        """Generate short-term improvement plan for high priority issues."""
        if not high_issues:
            return None
        
        # Group issues by component for efficient fixing
        component_groups = defaultdict(list)
        for issue in high_issues:
            primary_component = issue.affected_components[0] if issue.affected_components else 'unknown'
            component_groups[primary_component].append(issue)
        
        action_items = []
        user_actions = []
        
        # Create action items for each component group
        for component, component_issues in component_groups.items():
            # Create investigation phase
            investigation_action = ActionItem(
                id=f"investigate_{component}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title=f"Investigate {component} issues",
                description=f"Comprehensive analysis of {len(component_issues)} issues in {component}",
                priority=Priority.HIGH,
                estimated_time="1-2 days",
                assigned_to="development_team",
                dependencies=[],
                acceptance_criteria=[
                    "Root cause analysis completed",
                    "Fix strategy documented",
                    "Impact assessment finalized"
                ]
            )
            action_items.append(investigation_action)
            
            # Create fix implementation phase
            fix_action = ActionItem(
                id=f"fix_{component}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title=f"Fix {component} issues",
                description=f"Implement fixes for identified issues in {component}",
                priority=Priority.HIGH,
                estimated_time=self._estimate_component_fix_time(component_issues),
                assigned_to="development_team",
                dependencies=[investigation_action.id],
                acceptance_criteria=[
                    "All component issues resolved",
                    "Comprehensive testing completed",
                    "Performance benchmarks met",
                    "Documentation updated"
                ]
            )
            action_items.append(fix_action)
            
            # Create user action for component monitoring
            monitor_action = UserAction(
                id=f"monitor_{component}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title=f"Monitor {component} improvements",
                description=f"Track improvement progress for {component} component",
                urgency=Urgency.SOON,
                instructions=[
                    f"Review {component} metrics daily",
                    "Track issue resolution progress",
                    "Report any new issues immediately",
                    "Validate user experience improvements"
                ],
                expected_outcome=f"Stable and improved {component} functionality"
            )
            user_actions.append(monitor_action)
        
        # Calculate total resource requirements
        total_dev_hours = sum(self._estimate_fix_hours(issue) for issue in high_issues)
        total_testing_hours = total_dev_hours * 0.6  # 60% of dev time for testing
        
        resource_requirements = [
            ResourceRequirement(
                resource_type=ResourceType.DEVELOPER_TIME,
                quantity=total_dev_hours,
                unit="hours",
                availability="within_week"
            ),
            ResourceRequirement(
                resource_type=ResourceType.TESTING_TIME,
                quantity=total_testing_hours,
                unit="hours",
                availability="within_week"
            ),
            ResourceRequirement(
                resource_type=ResourceType.DOCUMENTATION,
                quantity=total_dev_hours * 0.2,  # 20% of dev time for documentation
                unit="hours",
                availability="available"
            )
        ]
        
        # Create timeline
        total_duration_days = (total_dev_hours / self.planning_config['developer_hours_per_day']) * 1.3  # 30% buffer
        timeline = Timeline(
            start_date=datetime.utcnow() + timedelta(days=1),  # Start after immediate fixes
            end_date=datetime.utcnow() + timedelta(days=total_duration_days + 1),
            milestones=[
                {
                    'name': 'Investigation phase complete',
                    'date': datetime.utcnow() + timedelta(days=3),
                    'description': 'All high priority issues analyzed'
                },
                {
                    'name': 'Implementation phase complete',
                    'date': datetime.utcnow() + timedelta(days=total_duration_days),
                    'description': 'All high priority fixes implemented'
                }
            ],
            dependencies=['immediate_fixes_complete'],
            critical_path=False
        )
        
        return ImprovementPlan(
            id=f"short_term_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Short-term High Priority Improvements",
            description=f"Resolution of {len(high_issues)} high priority issues across {len(component_groups)} components",
            plan_type=PlanType.SHORT_TERM,
            priority=Priority.HIGH,
            issues_addressed=[issue.id for issue in high_issues],
            action_items=action_items,
            user_actions=user_actions,
            resource_requirements=resource_requirements,
            timeline=timeline,
            success_metrics=[
                "All high priority issues resolved within 2 weeks",
                "System performance improved by 20%",
                "User satisfaction scores increased",
                "No critical regressions introduced"
            ],
            risk_assessment={
                'medium_risks': ['Resource conflicts', 'Scope creep', 'Integration complexity'],
                'mitigation_strategies': ['Clear prioritization', 'Regular progress reviews', 'Incremental delivery']
            },
            estimated_impact="Significant improvement in system reliability and user experience"
        )    

    async def _generate_long_term_plan(self, medium_low_issues: List[Issue]) -> Optional[ImprovementPlan]:
        """Generate long-term improvement plan for medium and low priority issues."""
        if not medium_low_issues:
            return None
        
        # Group issues by category for strategic planning
        category_groups = defaultdict(list)
        for issue in medium_low_issues:
            category_groups[issue.category].append(issue)
        
        action_items = []
        user_actions = []
        
        # Create strategic improvement phases
        for category, category_issues in category_groups.items():
            # Create planning phase
            planning_action = ActionItem(
                id=f"plan_{category.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title=f"Plan {category.value} improvements",
                description=f"Strategic planning for {len(category_issues)} {category.value} improvements",
                priority=Priority.MEDIUM,
                estimated_time="3-5 days",
                assigned_to="technical_lead",
                dependencies=[],
                acceptance_criteria=[
                    "Improvement roadmap created",
                    "Resource requirements identified",
                    "Implementation strategy defined"
                ]
            )
            action_items.append(planning_action)
            
            # Create implementation phase
            implementation_action = ActionItem(
                id=f"implement_{category.value}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title=f"Implement {category.value} improvements",
                description=f"Execute planned improvements for {category.value} issues",
                priority=Priority.MEDIUM,
                estimated_time=self._estimate_category_implementation_time(category_issues),
                assigned_to="development_team",
                dependencies=[planning_action.id],
                acceptance_criteria=[
                    "All planned improvements implemented",
                    "Quality standards met",
                    "Performance impact validated",
                    "User feedback incorporated"
                ]
            )
            action_items.append(implementation_action)
        
        # Create user action for long-term monitoring
        long_term_monitor = UserAction(
            id=f"long_term_monitor_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Long-term system improvement monitoring",
            description="Monitor overall system improvements and quality trends",
            urgency=Urgency.WHEN_CONVENIENT,
            instructions=[
                "Review monthly quality metrics",
                "Track improvement progress against roadmap",
                "Gather user feedback on improvements",
                "Adjust priorities based on business needs"
            ],
            expected_outcome="Continuous improvement in system quality and user satisfaction"
        )
        user_actions.append(long_term_monitor)
        
        # Calculate resource requirements
        total_dev_hours = sum(self._estimate_fix_hours(issue) for issue in medium_low_issues)
        
        resource_requirements = [
            ResourceRequirement(
                resource_type=ResourceType.DEVELOPER_TIME,
                quantity=total_dev_hours,
                unit="hours",
                availability="flexible"
            ),
            ResourceRequirement(
                resource_type=ResourceType.TESTING_TIME,
                quantity=total_dev_hours * 0.4,  # 40% of dev time for testing
                unit="hours",
                availability="flexible"
            )
        ]
        
        # Create timeline
        total_duration_days = min(
            (total_dev_hours / self.planning_config['developer_hours_per_day']) * 1.5,  # 50% buffer
            self.planning_config['max_plan_duration_days']
        )
        
        timeline = Timeline(
            start_date=datetime.utcnow() + timedelta(days=14),  # Start after short-term plan
            end_date=datetime.utcnow() + timedelta(days=total_duration_days + 14),
            milestones=[
                {
                    'name': 'Long-term planning complete',
                    'date': datetime.utcnow() + timedelta(days=21),
                    'description': 'Strategic improvement plans finalized'
                },
                {
                    'name': 'Phase 1 improvements complete',
                    'date': datetime.utcnow() + timedelta(days=total_duration_days / 2 + 14),
                    'description': 'First phase of improvements delivered'
                }
            ],
            dependencies=['short_term_plan_complete'],
            critical_path=False
        )
        
        return ImprovementPlan(
            id=f"long_term_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Long-term Quality Improvements",
            description=f"Strategic improvement of {len(medium_low_issues)} medium and low priority issues",
            plan_type=PlanType.LONG_TERM,
            priority=Priority.MEDIUM,
            issues_addressed=[issue.id for issue in medium_low_issues],
            action_items=action_items,
            user_actions=user_actions,
            resource_requirements=resource_requirements,
            timeline=timeline,
            success_metrics=[
                "All planned improvements delivered within timeline",
                "Overall system quality score improved by 15%",
                "Technical debt reduced significantly",
                "Development velocity increased"
            ],
            risk_assessment={
                'low_risks': ['Changing priorities', 'Resource reallocation'],
                'mitigation_strategies': ['Flexible planning', 'Regular priority reviews', 'Incremental delivery']
            },
            estimated_impact="Long-term improvement in system maintainability and developer productivity"
        )  
  
    async def _generate_preventive_plan(self, all_issues: List[Issue]) -> Optional[ImprovementPlan]:
        """Generate preventive measures plan to avoid future issues."""
        # Analyze patterns in issues to identify preventive measures
        issue_patterns = self._analyze_issue_patterns(all_issues)
        
        preventive_actions = []
        
        # Create monitoring improvements
        if issue_patterns.get('monitoring_gaps', 0) > 0:
            monitoring_action = ActionItem(
                id=f"improve_monitoring_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title="Enhance system monitoring and alerting",
                description="Implement comprehensive monitoring to detect issues early",
                priority=Priority.MEDIUM,
                estimated_time="1-2 weeks",
                assigned_to="devops_team",
                dependencies=[],
                acceptance_criteria=[
                    "Monitoring coverage increased to 95%",
                    "Alert thresholds optimized",
                    "Dashboard created for key metrics",
                    "On-call procedures updated"
                ]
            )
            preventive_actions.append(monitoring_action)
        
        # Create testing improvements
        if issue_patterns.get('testing_gaps', 0) > 0:
            testing_action = ActionItem(
                id=f"improve_testing_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title="Strengthen automated testing coverage",
                description="Expand test coverage to prevent regression issues",
                priority=Priority.MEDIUM,
                estimated_time="2-3 weeks",
                assigned_to="qa_team",
                dependencies=[],
                acceptance_criteria=[
                    "Test coverage increased to 90%",
                    "Integration tests expanded",
                    "Performance tests automated",
                    "Test execution time optimized"
                ]
            )
            preventive_actions.append(testing_action)
        
        # Create code quality improvements
        if issue_patterns.get('code_quality_issues', 0) > 0:
            quality_action = ActionItem(
                id=f"improve_code_quality_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title="Implement code quality standards",
                description="Establish and enforce code quality standards",
                priority=Priority.MEDIUM,
                estimated_time="1-2 weeks",
                assigned_to="technical_lead",
                dependencies=[],
                acceptance_criteria=[
                    "Code quality standards documented",
                    "Automated quality checks implemented",
                    "Code review process improved",
                    "Developer training completed"
                ]
            )
            preventive_actions.append(quality_action)
        
        if not preventive_actions:
            return None
        
        # Create user actions for preventive measures
        preventive_user_actions = [
            UserAction(
                id=f"preventive_monitoring_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title="Establish preventive monitoring routine",
                description="Regular monitoring to prevent issues before they occur",
                urgency=Urgency.WHEN_CONVENIENT,
                instructions=[
                    "Review system health metrics weekly",
                    "Analyze trends for early warning signs",
                    "Update monitoring thresholds based on patterns",
                    "Conduct monthly preventive maintenance"
                ],
                expected_outcome="Proactive issue prevention and early detection"
            )
        ]
        
        resource_requirements = [
            ResourceRequirement(
                resource_type=ResourceType.DEVELOPER_TIME,
                quantity=80,  # Estimated hours for preventive measures
                unit="hours",
                availability="flexible"
            ),
            ResourceRequirement(
                resource_type=ResourceType.INFRASTRUCTURE,
                quantity=2,
                unit="instances",
                availability="available"
            )
        ]
        
        timeline = Timeline(
            start_date=datetime.utcnow() + timedelta(days=30),  # Start after other plans
            end_date=datetime.utcnow() + timedelta(days=60),
            milestones=[
                {
                    'name': 'Preventive measures implemented',
                    'date': datetime.utcnow() + timedelta(days=45),
                    'description': 'All preventive measures in place'
                }
            ],
            dependencies=['long_term_plan_started'],
            critical_path=False
        )
        
        return ImprovementPlan(
            id=f"preventive_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Preventive Quality Measures",
            description="Implement preventive measures to avoid future issues",
            plan_type=PlanType.PREVENTIVE,
            priority=Priority.MEDIUM,
            issues_addressed=[],  # Preventive, not addressing specific issues
            action_items=preventive_actions,
            user_actions=preventive_user_actions,
            resource_requirements=resource_requirements,
            timeline=timeline,
            success_metrics=[
                "Issue detection time reduced by 50%",
                "Number of critical issues reduced by 30%",
                "System uptime improved to 99.9%",
                "Developer productivity increased"
            ],
            risk_assessment={
                'low_risks': ['Implementation complexity', 'Resource availability'],
                'mitigation_strategies': ['Phased implementation', 'Training and documentation']
            },
            estimated_impact="Significant reduction in future issues and improved system reliability"
        )   
 
    async def _generate_comprehensive_user_actions(self, issues: List[Issue]) -> List[UserAction]:
        """Generate comprehensive user actions for all issues."""
        user_actions = []
        
        # Create immediate monitoring actions for critical issues
        critical_issues = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        if critical_issues:
            critical_monitoring = UserAction(
                id=f"critical_monitoring_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title="Critical Issue Monitoring",
                description="Immediate monitoring of critical system issues",
                urgency=Urgency.IMMEDIATE,
                instructions=[
                    "Monitor system status every 15 minutes",
                    "Check error logs continuously",
                    "Escalate any degradation immediately",
                    "Communicate status to all stakeholders",
                    "Prepare rollback procedures if needed"
                ],
                expected_outcome="Critical issues contained and resolved quickly"
            )
            user_actions.append(critical_monitoring)
        
        # Create communication actions
        if len(issues) > 5:  # If many issues, need communication plan
            communication_action = UserAction(
                id=f"communication_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                title="Stakeholder Communication Plan",
                description="Communicate improvement plans to stakeholders",
                urgency=Urgency.SOON,
                instructions=[
                    "Prepare executive summary of issues and plans",
                    "Schedule stakeholder briefing meeting",
                    "Create regular progress update schedule",
                    "Establish escalation communication channels",
                    "Document lessons learned for future reference"
                ],
                expected_outcome="Clear stakeholder understanding and support for improvement plans"
            )
            user_actions.append(communication_action)
        
        # Create resource coordination actions
        resource_coordination = UserAction(
            id=f"resource_coordination_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Resource Coordination and Planning",
            description="Coordinate resources for improvement plan execution",
            urgency=Urgency.SOON,
            instructions=[
                "Confirm developer availability for critical fixes",
                "Schedule testing resources for validation",
                "Coordinate with external service providers if needed",
                "Prepare backup resources for contingencies",
                "Track resource utilization against plan"
            ],
            expected_outcome="Adequate resources available for timely issue resolution"
        )
        user_actions.append(resource_coordination)
        
        # Create quality assurance actions
        qa_action = UserAction(
            id=f"quality_assurance_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            title="Quality Assurance and Validation",
            description="Ensure quality of implemented fixes and improvements",
            urgency=Urgency.WHEN_CONVENIENT,
            instructions=[
                "Review all fixes before deployment",
                "Validate fixes against acceptance criteria",
                "Conduct user acceptance testing",
                "Monitor post-deployment metrics",
                "Document validation results"
            ],
            expected_outcome="High quality fixes with no regressions"
        )
        user_actions.append(qa_action)
        
        return user_actions
    
    # Helper methods for calculations and analysis
    def _estimate_fix_hours(self, issue: Issue) -> float:
        """Estimate hours required to fix an issue."""
        effort_model = self.effort_models.get(issue.category, self.effort_models[IssueCategory.FUNCTIONALITY])
        severity_model = effort_model.get(issue.severity, effort_model[IssueSeverity.MEDIUM])
        
        # Base estimate
        base_hours = (severity_model['min_hours'] + severity_model['max_hours']) / 2
        
        # Apply complexity factor based on affected components
        complexity_factor = severity_model['complexity_factor']
        if len(issue.affected_components) > 1:
            complexity_factor *= 1.2  # 20% increase for multi-component issues
        
        return base_hours * complexity_factor
    
    def _estimate_component_fix_time(self, component_issues: List[Issue]) -> str:
        """Estimate time to fix all issues in a component."""
        total_hours = sum(self._estimate_fix_hours(issue) for issue in component_issues)
        total_days = total_hours / self.planning_config['developer_hours_per_day']
        
        if total_days <= 1:
            return "1 day"
        elif total_days <= 7:
            return f"{int(total_days)}-{int(total_days) + 1} days"
        else:
            return f"{int(total_days / 7)}-{int(total_days / 7) + 1} weeks"
    
    def _estimate_category_implementation_time(self, category_issues: List[Issue]) -> str:
        """Estimate implementation time for a category of issues."""
        total_hours = sum(self._estimate_fix_hours(issue) for issue in category_issues)
        total_weeks = total_hours / (self.planning_config['developer_hours_per_day'] * 5)  # 5 working days per week
        
        if total_weeks <= 1:
            return "1 week"
        elif total_weeks <= 4:
            return f"{int(total_weeks)}-{int(total_weeks) + 1} weeks"
        else:
            return f"{int(total_weeks / 4)}-{int(total_weeks / 4) + 1} months"
    
    def _analyze_issue_patterns(self, issues: List[Issue]) -> Dict[str, int]:
        """Analyze patterns in issues to identify preventive measures needed."""
        patterns = {
            'monitoring_gaps': 0,
            'testing_gaps': 0,
            'code_quality_issues': 0,
            'integration_issues': 0,
            'performance_issues': 0
        }
        
        for issue in issues:
            # Simple pattern detection based on issue characteristics
            if 'monitoring' in issue.description.lower() or 'alert' in issue.description.lower():
                patterns['monitoring_gaps'] += 1
            if 'test' in issue.description.lower() or 'coverage' in issue.description.lower():
                patterns['testing_gaps'] += 1
            if issue.category == IssueCategory.PERFORMANCE:
                patterns['performance_issues'] += 1
            if 'integration' in issue.description.lower() or 'api' in issue.description.lower():
                patterns['integration_issues'] += 1
            if issue.category == IssueCategory.FUNCTIONALITY and len(issue.affected_components) > 1:
                patterns['code_quality_issues'] += 1
        
        return patterns
    
    def _assess_overall_business_impact(self, issues: List[Issue]) -> str:
        """Assess overall business impact of all issues."""
        critical_count = len([i for i in issues if i.severity == IssueSeverity.CRITICAL])
        high_count = len([i for i in issues if i.severity == IssueSeverity.HIGH])
        
        if critical_count > 0:
            return "CRITICAL - Immediate business impact with potential service disruption"
        elif high_count > 3:
            return "HIGH - Significant impact on user experience and business operations"
        elif high_count > 0:
            return "MEDIUM - Moderate impact on system reliability and user satisfaction"
        else:
            return "LOW - Minor impact on system quality and maintainability"    
 
   async def _generate_immediate_recommendations(self, critical_issues: List[Issue]) -> List[str]:
        """Generate immediate action recommendations for critical issues."""
        if not critical_issues:
            return ["No critical issues identified - continue with planned improvements"]
        
        recommendations = [
            "Assemble emergency response team immediately",
            "Prioritize critical issue resolution over all other work",
            "Implement continuous monitoring during fix deployment",
            "Prepare rollback procedures for all critical fixes",
            "Communicate status to stakeholders every 2 hours"
        ]
        
        # Add specific recommendations based on issue types
        security_issues = [i for i in critical_issues if i.category == IssueCategory.SECURITY]
        if security_issues:
            recommendations.append("Consider temporary service restrictions to mitigate security risks")
        
        performance_issues = [i for i in critical_issues if i.category == IssueCategory.PERFORMANCE]
        if performance_issues:
            recommendations.append("Scale infrastructure resources immediately to handle performance issues")
        
        return recommendations
    
    async def _generate_short_term_recommendations(self, high_issues: List[Issue]) -> List[str]:
        """Generate short-term action recommendations for high priority issues."""
        if not high_issues:
            return ["Focus on medium and low priority improvements"]
        
        return [
            "Allocate dedicated development resources for high priority fixes",
            "Implement enhanced testing procedures for all fixes",
            "Establish daily progress review meetings",
            "Create detailed fix validation procedures",
            "Plan for gradual rollout of fixes to minimize risk"
        ]
    
    async def _identify_resource_needs(self, issues: List[Issue]) -> List[str]:
        """Identify specific resource needs for issue resolution."""
        total_dev_hours = sum(self._estimate_fix_hours(issue) for issue in issues)
        
        needs = []
        
        if total_dev_hours > 200:
            needs.append("Additional senior developer resources required")
        if len([i for i in issues if i.category == IssueCategory.SECURITY]) > 0:
            needs.append("Security specialist consultation needed")
        if len([i for i in issues if i.category == IssueCategory.PERFORMANCE]) > 2:
            needs.append("Performance engineering expertise required")
        if len([i for i in issues if 'integration' in i.description.lower()]) > 0:
            needs.append("External service coordination may be needed")
        
        return needs or ["Current team resources should be sufficient"]
    
    async def _identify_risk_mitigation_strategies(self, issues: List[Issue]) -> List[str]:
        """Identify risk mitigation strategies for issue resolution."""
        strategies = [
            "Implement comprehensive testing for all fixes",
            "Maintain rollback procedures for all deployments",
            "Use feature flags for gradual rollout of fixes",
            "Establish clear escalation procedures",
            "Document all changes for future reference"
        ]
        
        # Add specific strategies based on issue patterns
        if len([i for i in issues if len(i.affected_components) > 1]) > 2:
            strategies.append("Focus on component isolation to prevent cascading failures")
        
        if len([i for i in issues if i.category == IssueCategory.PERFORMANCE]) > 0:
            strategies.append("Implement performance monitoring for early detection of regressions")
        
        return strategies
    
    async def _create_implementation_timeline(self) -> Dict[str, Any]:
        """Create comprehensive implementation timeline."""
        if not self.improvement_plans:
            return {}
        
        # Calculate overall timeline
        earliest_start = min(plan.timeline.start_date for plan in self.improvement_plans)
        latest_end = max(plan.timeline.end_date for plan in self.improvement_plans)
        total_duration_days = (latest_end - earliest_start).days
        
        # Create implementation phases
        phases = []
        
        # Phase 1: Immediate fixes (if any)
        immediate_plans = [p for p in self.improvement_plans if p.plan_type == PlanType.IMMEDIATE_FIXES]
        if immediate_plans:
            phases.append(ImplementationPhase(
                phase_name="Emergency Response",
                description="Immediate resolution of critical issues",
                duration_days=1,
                prerequisites=["Development team available", "Rollback procedures ready"],
                deliverables=["Critical issues resolved", "System stability restored"],
                success_criteria=["All critical issues fixed", "No new critical issues"],
                risks=["Potential regressions", "Resource availability"]
            ))
        
        # Phase 2: Short-term improvements
        short_term_plans = [p for p in self.improvement_plans if p.plan_type == PlanType.SHORT_TERM]
        if short_term_plans:
            phases.append(ImplementationPhase(
                phase_name="Short-term Stabilization",
                description="Resolution of high priority issues",
                duration_days=14,
                prerequisites=["Critical issues resolved", "Resources allocated"],
                deliverables=["High priority issues fixed", "System performance improved"],
                success_criteria=["All high priority issues resolved", "Performance targets met"],
                risks=["Scope creep", "Resource conflicts"]
            ))
        
        # Phase 3: Long-term improvements
        long_term_plans = [p for p in self.improvement_plans if p.plan_type == PlanType.LONG_TERM]
        if long_term_plans:
            phases.append(ImplementationPhase(
                phase_name="Strategic Improvements",
                description="Long-term quality and performance improvements",
                duration_days=60,
                prerequisites=["Short-term issues resolved", "Strategic plan approved"],
                deliverables=["Quality improvements implemented", "Technical debt reduced"],
                success_criteria=["Quality metrics improved", "Developer productivity increased"],
                risks=["Changing priorities", "Resource reallocation"]
            ))
        
        # Phase 4: Preventive measures
        preventive_plans = [p for p in self.improvement_plans if p.plan_type == PlanType.PREVENTIVE]
        if preventive_plans:
            phases.append(ImplementationPhase(
                phase_name="Preventive Measures",
                description="Implementation of preventive quality measures",
                duration_days=30,
                prerequisites=["Core improvements complete", "Monitoring infrastructure ready"],
                deliverables=["Monitoring enhanced", "Quality processes improved"],
                success_criteria=["Early detection capability", "Reduced issue frequency"],
                risks=["Implementation complexity", "Training requirements"]
            ))
        
        return {
            'total_duration_days': total_duration_days,
            'start_date': earliest_start.isoformat(),
            'end_date': latest_end.isoformat(),
            'phases': phases,
            'critical_path': self._identify_critical_path(),
            'milestones': self._extract_all_milestones(),
            'dependencies': self._map_dependencies()
        }
    
    async def _calculate_resource_summary(self) -> Dict[str, Any]:
        """Calculate comprehensive resource requirements summary."""
        resource_summary = defaultdict(lambda: {'total_quantity': 0, 'peak_demand': 0, 'availability_status': 'unknown'})
        
        for plan in self.improvement_plans:
            for requirement in plan.resource_requirements:
                resource_type = requirement.resource_type.value
                resource_summary[resource_type]['total_quantity'] += requirement.quantity
                resource_summary[resource_type]['peak_demand'] = max(
                    resource_summary[resource_type]['peak_demand'],
                    requirement.quantity
                )
                
                # Update availability status (most restrictive wins)
                current_availability = resource_summary[resource_type]['availability_status']
                if current_availability == 'unknown' or requirement.availability == 'immediate':
                    resource_summary[resource_type]['availability_status'] = requirement.availability
        
        # Check capacity constraints
        capacity_analysis = {}
        for resource_type, summary in resource_summary.items():
            resource_enum = ResourceType(resource_type)
            available_capacity = self.resource_capacity.get(resource_enum, 0)
            
            capacity_analysis[resource_type] = {
                'required': summary['total_quantity'],
                'available': available_capacity,
                'utilization_percentage': (summary['total_quantity'] / available_capacity * 100) if available_capacity > 0 else 0,
                'capacity_sufficient': summary['total_quantity'] <= available_capacity,
                'peak_demand': summary['peak_demand'],
                'availability_status': summary['availability_status']
            }
        
        return {
            'resource_requirements': dict(resource_summary),
            'capacity_analysis': capacity_analysis,
            'resource_constraints': [
                resource_type for resource_type, analysis in capacity_analysis.items()
                if not analysis['capacity_sufficient']
            ],
            'recommendations': self._generate_resource_recommendations(capacity_analysis)
        }
    
    async def _generate_success_metrics(self, issues: List[Issue]) -> List[str]:
        """Generate success metrics for improvement plans."""
        metrics = []
        
        # Issue resolution metrics
        critical_count = len([i for i in issues if i.severity == IssueSeverity.CRITICAL])
        high_count = len([i for i in issues if i.severity == IssueSeverity.HIGH])
        
        if critical_count > 0:
            metrics.append(f"All {critical_count} critical issues resolved within 24 hours")
        if high_count > 0:
            metrics.append(f"All {high_count} high priority issues resolved within 2 weeks")
        
        # Performance metrics
        metrics.extend([
            "System uptime improved to 99.9%",
            "Average response time reduced by 30%",
            "Error rate reduced to below 1%",
            "User satisfaction score increased by 20%"
        ])
        
        # Quality metrics
        metrics.extend([
            "Test coverage increased to 90%",
            "Code quality score improved by 25%",
            "Technical debt reduced by 40%",
            "Security vulnerabilities reduced to zero"
        ])
        
        # Business metrics
        metrics.extend([
            "Customer complaints reduced by 50%",
            "Support ticket volume reduced by 30%",
            "Development velocity increased by 15%",
            "Time to market for new features improved by 20%"
        ])
        
        return metrics
    
    def _identify_critical_path(self) -> List[str]:
        """Identify critical path through improvement plans."""
        critical_path = []
        
        for plan in self.improvement_plans:
            if plan.timeline.critical_path or plan.plan_type == PlanType.IMMEDIATE_FIXES:
                critical_path.append(plan.title)
        
        return critical_path
    
    def _extract_all_milestones(self) -> List[Dict[str, Any]]:
        """Extract all milestones from improvement plans."""
        all_milestones = []
        
        for plan in self.improvement_plans:
            for milestone in plan.timeline.milestones:
                milestone_with_plan = milestone.copy()
                milestone_with_plan['plan'] = plan.title
                all_milestones.append(milestone_with_plan)
        
        # Sort by date
        all_milestones.sort(key=lambda x: x['date'])
        
        return all_milestones
    
    def _map_dependencies(self) -> Dict[str, List[str]]:
        """Map dependencies between improvement plans."""
        dependencies = {}
        
        for plan in self.improvement_plans:
            dependencies[plan.title] = plan.timeline.dependencies
        
        return dependencies
    
    def _generate_resource_recommendations(self, capacity_analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations for resource management."""
        recommendations = []
        
        for resource_type, analysis in capacity_analysis.items():
            if not analysis['capacity_sufficient']:
                if analysis['utilization_percentage'] > 150:
                    recommendations.append(f"URGENT: {resource_type} capacity severely exceeded - consider external resources")
                elif analysis['utilization_percentage'] > 100:
                    recommendations.append(f"WARNING: {resource_type} capacity exceeded - prioritize or extend timeline")
            elif analysis['utilization_percentage'] > 80:
                recommendations.append(f"CAUTION: {resource_type} utilization high - monitor closely")
        
        if not recommendations:
            recommendations.append("Resource capacity appears sufficient for planned improvements")
        
        return recommendations