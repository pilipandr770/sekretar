"""
Test Orchestrator Framework

Coordinates execution of comprehensive system tests with real data integration.
"""
import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import traceback
import json
import os

from tests.infrastructure.test_data_manager import TestDataManager
from tests.infrastructure.test_environment import TestEnvironment
from tests.infrastructure.models import (
    TestResult, TestSuiteResult, ComprehensiveReport,
    TestStatus, Issue, ActionItem, UserAction,
    IssueSeverity, IssueCategory, Priority, Urgency
)


class TestCategory(Enum):
    """Test category enumeration."""
    USER_REGISTRATION = "user_registration"
    API_ENDPOINTS = "api_endpoints"
    CRM_FUNCTIONALITY = "crm_functionality"
    KYB_MONITORING = "kyb_monitoring"
    AI_AGENTS = "ai_agents"
    BILLING = "billing"
    CALENDAR = "calendar"
    KNOWLEDGE = "knowledge"
    COMMUNICATION = "communication"
    INTEGRATION = "integration"
    PERFORMANCE = "performance"
    SECURITY = "security"


@dataclass
class TestExecutionContext:
    """Context for test execution."""
    test_environment: TestEnvironment
    test_data_manager: TestDataManager
    real_company_data: Dict[str, Any]
    execution_start_time: datetime
    current_test_suite: Optional[str] = None
    current_test: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class TestOrchestrator:
    """
    Main orchestrator for comprehensive system testing.
    
    Coordinates test execution, manages test environment,
    and generates comprehensive reports with improvement plans.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize test orchestrator."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.test_environment = TestEnvironment(self.config.get('environment', {}))
        self.test_data_manager = TestDataManager(self.config.get('data_manager', {}))
        
        # Test registry
        self.test_suites: Dict[TestCategory, List[Callable]] = {}
        self.test_results: List[TestSuiteResult] = []
        self.execution_context: Optional[TestExecutionContext] = None
        
        # Performance tracking
        self.performance_metrics = {
            'total_execution_time': 0.0,
            'setup_time': 0.0,
            'cleanup_time': 0.0,
            'test_execution_time': 0.0,
            'data_preparation_time': 0.0
        }
        
        # Issue tracking
        self.detected_issues: List[Issue] = []
        self.improvement_actions: List[ActionItem] = []
        self.user_actions: List[UserAction] = []
    
    def register_test_suite(self, category: TestCategory, test_functions: List[Callable]):
        """Register test suite for a category."""
        if category not in self.test_suites:
            self.test_suites[category] = []
        self.test_suites[category].extend(test_functions)
        self.logger.info(f"Registered {len(test_functions)} tests for category {category.value}")
    
    async def run_comprehensive_test_suite(self) -> ComprehensiveReport:
        """
        Run the complete comprehensive test suite.
        
        Returns:
            ComprehensiveReport: Detailed report with findings and recommendations
        """
        start_time = time.time()
        self.logger.info("Starting comprehensive test suite execution")
        
        try:
            # Phase 1: Setup
            setup_start = time.time()
            await self._setup_test_environment()
            self.performance_metrics['setup_time'] = time.time() - setup_start
            
            # Phase 2: Data Preparation
            data_prep_start = time.time()
            real_company_data = await self._prepare_real_company_data()
            self.performance_metrics['data_preparation_time'] = time.time() - data_prep_start
            
            # Phase 3: Test Execution
            test_exec_start = time.time()
            await self._execute_all_test_suites(real_company_data)
            self.performance_metrics['test_execution_time'] = time.time() - test_exec_start
            
            # Phase 4: Analysis and Reporting
            report = await self._generate_comprehensive_report()
            
            return report
            
        except Exception as e:
            self.logger.error(f"Critical error during test execution: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Create emergency report
            return self._create_emergency_report(str(e))
            
        finally:
            # Phase 5: Cleanup
            cleanup_start = time.time()
            await self._cleanup_test_environment()
            self.performance_metrics['cleanup_time'] = time.time() - cleanup_start
            
            self.performance_metrics['total_execution_time'] = time.time() - start_time
            self.logger.info(f"Test suite completed in {self.performance_metrics['total_execution_time']:.2f}s")
    
    async def _setup_test_environment(self) -> bool:
        """Setup isolated test environment."""
        self.logger.info("Setting up test environment")
        
        try:
            # Initialize test environment
            success = await self.test_environment.setup()
            if not success:
                raise RuntimeError("Failed to setup test environment")
            
            # Initialize test data manager
            await self.test_data_manager.initialize()
            
            # Create execution context
            self.execution_context = TestExecutionContext(
                test_environment=self.test_environment,
                test_data_manager=self.test_data_manager,
                real_company_data={},
                execution_start_time=datetime.utcnow()
            )
            
            self.logger.info("Test environment setup completed successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to setup test environment: {str(e)}")
            raise
    
    async def _prepare_real_company_data(self) -> Dict[str, Any]:
        """Prepare real company data for testing."""
        self.logger.info("Preparing real company data")
        
        try:
            # Collect real company data from various sources
            company_data = await self.test_data_manager.collect_real_company_data()
            
            # Validate and prepare data
            validated_data = await self.test_data_manager.validate_company_data(company_data)
            
            # Store in execution context
            if self.execution_context:
                self.execution_context.real_company_data = validated_data
            
            self.logger.info(f"Prepared data for {len(validated_data)} companies")
            return validated_data
            
        except Exception as e:
            self.logger.error(f"Failed to prepare company data: {str(e)}")
            raise
    
    async def _execute_all_test_suites(self, real_company_data: Dict[str, Any]):
        """Execute all registered test suites."""
        self.logger.info("Executing all test suites")
        
        # Define execution order for test categories
        execution_order = [
            TestCategory.USER_REGISTRATION,
            TestCategory.API_ENDPOINTS,
            TestCategory.CRM_FUNCTIONALITY,
            TestCategory.KYB_MONITORING,
            TestCategory.AI_AGENTS,
            TestCategory.BILLING,
            TestCategory.CALENDAR,
            TestCategory.KNOWLEDGE,
            TestCategory.COMMUNICATION,
            TestCategory.INTEGRATION,
            TestCategory.PERFORMANCE,
            TestCategory.SECURITY
        ]
        
        for category in execution_order:
            if category in self.test_suites:
                suite_result = await self._execute_test_suite(category, real_company_data)
                self.test_results.append(suite_result)
    
    async def _execute_test_suite(self, category: TestCategory, real_company_data: Dict[str, Any]) -> TestSuiteResult:
        """Execute a specific test suite."""
        suite_start_time = time.time()
        self.logger.info(f"Executing test suite: {category.value}")
        
        if self.execution_context:
            self.execution_context.current_test_suite = category.value
        
        test_functions = self.test_suites[category]
        test_results = []
        
        passed = failed = skipped = errors = 0
        
        for test_func in test_functions:
            test_result = await self._execute_single_test(test_func, real_company_data)
            test_results.append(test_result)
            
            # Update counters
            if test_result.status == TestStatus.PASSED:
                passed += 1
            elif test_result.status == TestStatus.FAILED:
                failed += 1
            elif test_result.status == TestStatus.SKIPPED:
                skipped += 1
            elif test_result.status == TestStatus.ERROR:
                errors += 1
        
        execution_time = time.time() - suite_start_time
        
        suite_result = TestSuiteResult(
            suite_name=category.value,
            total_tests=len(test_functions),
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            execution_time=execution_time,
            test_results=test_results
        )
        
        self.logger.info(f"Test suite {category.value} completed: {passed} passed, {failed} failed, {errors} errors")
        return suite_result
    
    async def _execute_single_test(self, test_func: Callable, real_company_data: Dict[str, Any]) -> TestResult:
        """Execute a single test function."""
        test_start_time = time.time()
        test_name = getattr(test_func, '__name__', str(test_func))
        
        if self.execution_context:
            self.execution_context.current_test = test_name
        
        self.logger.debug(f"Executing test: {test_name}")
        
        try:
            # Execute test function with context
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func(self.execution_context, real_company_data)
            else:
                result = test_func(self.execution_context, real_company_data)
            
            execution_time = time.time() - test_start_time
            
            # Determine test status based on result
            if result is True or (isinstance(result, dict) and result.get('success', False)):
                status = TestStatus.PASSED
                error_message = None
                details = result if isinstance(result, dict) else {}
            else:
                status = TestStatus.FAILED
                error_message = result.get('error', 'Test failed') if isinstance(result, dict) else 'Test returned False'
                details = result if isinstance(result, dict) else {'result': result}
            
            return TestResult(
                test_name=test_name,
                status=status,
                execution_time=execution_time,
                error_message=error_message,
                details=details,
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            execution_time = time.time() - test_start_time
            error_message = str(e)
            
            self.logger.error(f"Test {test_name} failed with exception: {error_message}")
            self.logger.debug(traceback.format_exc())
            
            return TestResult(
                test_name=test_name,
                status=TestStatus.ERROR,
                execution_time=execution_time,
                error_message=error_message,
                details={'exception': traceback.format_exc()},
                timestamp=datetime.utcnow()
            )
    
    async def _generate_comprehensive_report(self) -> ComprehensiveReport:
        """Generate comprehensive test report with analysis."""
        self.logger.info("Generating comprehensive report")
        
        # Analyze test results for issues
        await self._analyze_test_results()
        
        # Generate improvement plan
        await self._generate_improvement_plan()
        
        # Determine overall status
        overall_status = self._determine_overall_status()
        
        report = ComprehensiveReport(
            overall_status=overall_status,
            total_execution_time=self.performance_metrics['total_execution_time'],
            suite_results=self.test_results,
            critical_issues=self.detected_issues,
            improvement_plan=self.improvement_actions,
            user_action_required=self.user_actions
        )
        
        # Save report to file
        await self._save_report_to_file(report)
        
        return report
    
    async def _analyze_test_results(self):
        """Analyze test results to identify issues."""
        self.logger.info("Analyzing test results for issues")
        
        for suite_result in self.test_results:
            for test_result in suite_result.test_results:
                if test_result.status in [TestStatus.FAILED, TestStatus.ERROR]:
                    issue = self._create_issue_from_test_result(test_result, suite_result.suite_name)
                    self.detected_issues.append(issue)
    
    def _create_issue_from_test_result(self, test_result: TestResult, suite_name: str) -> Issue:
        """Create issue from failed test result."""
        # Determine severity based on test category and error type
        severity = self._determine_issue_severity(test_result, suite_name)
        category = self._determine_issue_category(test_result, suite_name)
        
        return Issue(
            id=f"{suite_name}_{test_result.test_name}_{int(test_result.timestamp.timestamp())}",
            severity=severity,
            category=category,
            title=f"Test failure in {test_result.test_name}",
            description=test_result.error_message or "Test failed without specific error message",
            affected_components=[suite_name],
            reproduction_steps=[
                f"Run test suite: {suite_name}",
                f"Execute test: {test_result.test_name}",
                "Review test output and logs"
            ],
            expected_behavior="Test should pass successfully",
            actual_behavior=test_result.error_message or "Test failed",
            fix_priority=self._calculate_fix_priority(severity, category),
            estimated_effort=self._estimate_fix_effort(test_result, suite_name)
        )
    
    def _determine_issue_severity(self, test_result: TestResult, suite_name: str) -> IssueSeverity:
        """Determine issue severity based on test context."""
        # Critical issues
        if suite_name in ['user_registration', 'api_endpoints', 'security']:
            return IssueSeverity.CRITICAL
        
        # High priority issues
        if suite_name in ['crm_functionality', 'kyb_monitoring', 'billing']:
            return IssueSeverity.HIGH
        
        # Medium priority issues
        if suite_name in ['ai_agents', 'calendar', 'knowledge']:
            return IssueSeverity.MEDIUM
        
        # Low priority issues
        return IssueSeverity.LOW
    
    def _determine_issue_category(self, test_result: TestResult, suite_name: str) -> IssueCategory:
        """Determine issue category based on test context."""
        if suite_name == 'security':
            return IssueCategory.SECURITY
        elif suite_name == 'performance':
            return IssueCategory.PERFORMANCE
        elif 'ui' in test_result.test_name.lower() or 'interface' in test_result.test_name.lower():
            return IssueCategory.USABILITY
        else:
            return IssueCategory.FUNCTIONALITY
    
    def _calculate_fix_priority(self, severity: IssueSeverity, category: IssueCategory) -> int:
        """Calculate fix priority score."""
        severity_weights = {
            IssueSeverity.CRITICAL: 100,
            IssueSeverity.HIGH: 75,
            IssueSeverity.MEDIUM: 50,
            IssueSeverity.LOW: 25
        }
        
        category_weights = {
            IssueCategory.SECURITY: 20,
            IssueCategory.FUNCTIONALITY: 15,
            IssueCategory.PERFORMANCE: 10,
            IssueCategory.USABILITY: 5
        }
        
        return severity_weights[severity] + category_weights[category]
    
    def _estimate_fix_effort(self, test_result: TestResult, suite_name: str) -> str:
        """Estimate effort required to fix the issue."""
        # Simple heuristic based on error type and test category
        if test_result.status == TestStatus.ERROR:
            return "2-4 hours"  # Likely code fix needed
        elif 'integration' in suite_name or 'api' in suite_name:
            return "4-8 hours"  # Integration issues take longer
        else:
            return "1-2 hours"  # Simple functionality fix
    
    async def _generate_improvement_plan(self):
        """Generate improvement plan based on detected issues."""
        self.logger.info("Generating improvement plan")
        
        # Sort issues by priority
        sorted_issues = sorted(self.detected_issues, key=lambda x: x.fix_priority, reverse=True)
        
        # Create action items for high-priority issues
        for issue in sorted_issues[:10]:  # Top 10 issues
            action_item = ActionItem(
                id=f"action_{issue.id}",
                title=f"Fix: {issue.title}",
                description=f"Address {issue.severity.value} severity issue in {', '.join(issue.affected_components)}",
                priority=self._map_severity_to_priority(issue.severity),
                estimated_time=issue.estimated_effort,
                assigned_to="Development Team",
                dependencies=[],
                acceptance_criteria=[
                    f"Test {issue.title.split()[-1]} passes successfully",
                    "No regression in related functionality",
                    "Code review completed"
                ]
            )
            self.improvement_actions.append(action_item)
        
        # Create user actions for critical issues
        critical_issues = [i for i in sorted_issues if i.severity == IssueSeverity.CRITICAL]
        for issue in critical_issues:
            user_action = UserAction(
                id=f"user_action_{issue.id}",
                title=f"Review Critical Issue: {issue.title}",
                description=f"Critical issue detected that requires immediate attention",
                urgency=Urgency.IMMEDIATE,
                instructions=[
                    f"Review test failure: {issue.title}",
                    f"Check affected components: {', '.join(issue.affected_components)}",
                    "Prioritize fix in next sprint",
                    "Consider hotfix if affecting production"
                ],
                expected_outcome="Issue is triaged and fix is scheduled"
            )
            self.user_actions.append(user_action)
    
    def _map_severity_to_priority(self, severity: IssueSeverity) -> Priority:
        """Map issue severity to action priority."""
        mapping = {
            IssueSeverity.CRITICAL: Priority.HIGH,
            IssueSeverity.HIGH: Priority.HIGH,
            IssueSeverity.MEDIUM: Priority.MEDIUM,
            IssueSeverity.LOW: Priority.LOW
        }
        return mapping[severity]
    
    def _determine_overall_status(self) -> str:
        """Determine overall system status based on test results."""
        total_tests = sum(suite.total_tests for suite in self.test_results)
        total_failed = sum(suite.failed for suite in self.test_results)
        total_errors = sum(suite.errors for suite in self.test_results)
        
        critical_issues = len([i for i in self.detected_issues if i.severity == IssueSeverity.CRITICAL])
        
        if critical_issues > 0:
            return "CRITICAL_ISSUES_DETECTED"
        elif total_errors > 0:
            return "ERRORS_DETECTED"
        elif total_failed > total_tests * 0.1:  # More than 10% failure rate
            return "HIGH_FAILURE_RATE"
        elif total_failed > 0:
            return "SOME_ISSUES_DETECTED"
        else:
            return "ALL_TESTS_PASSED"
    
    async def _save_report_to_file(self, report: ComprehensiveReport):
        """Save comprehensive report to file."""
        try:
            # Create reports directory if it doesn't exist
            reports_dir = "test_reports"
            os.makedirs(reports_dir, exist_ok=True)
            
            # Generate filename with timestamp
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            filename = f"{reports_dir}/comprehensive_test_report_{timestamp}.json"
            
            # Convert report to dict for JSON serialization
            report_dict = self._report_to_dict(report)
            
            # Save to file
            with open(filename, 'w') as f:
                json.dump(report_dict, f, indent=2, default=str)
            
            self.logger.info(f"Report saved to {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to save report to file: {str(e)}")
    
    def _report_to_dict(self, report: ComprehensiveReport) -> Dict[str, Any]:
        """Convert report to dictionary for JSON serialization."""
        return {
            'overall_status': report.overall_status,
            'total_execution_time': report.total_execution_time,
            'suite_results': [
                {
                    'suite_name': suite.suite_name,
                    'total_tests': suite.total_tests,
                    'passed': suite.passed,
                    'failed': suite.failed,
                    'skipped': suite.skipped,
                    'errors': suite.errors,
                    'execution_time': suite.execution_time,
                    'test_results': [
                        {
                            'test_name': test.test_name,
                            'status': test.status.value,
                            'execution_time': test.execution_time,
                            'error_message': test.error_message,
                            'details': test.details,
                            'timestamp': test.timestamp.isoformat()
                        }
                        for test in suite.test_results
                    ]
                }
                for suite in report.suite_results
            ],
            'critical_issues': [
                {
                    'id': issue.id,
                    'severity': issue.severity.value,
                    'category': issue.category.value,
                    'title': issue.title,
                    'description': issue.description,
                    'affected_components': issue.affected_components,
                    'reproduction_steps': issue.reproduction_steps,
                    'expected_behavior': issue.expected_behavior,
                    'actual_behavior': issue.actual_behavior,
                    'fix_priority': issue.fix_priority,
                    'estimated_effort': issue.estimated_effort
                }
                for issue in report.critical_issues
            ],
            'improvement_plan': [
                {
                    'id': action.id,
                    'title': action.title,
                    'description': action.description,
                    'priority': action.priority.value,
                    'estimated_time': action.estimated_time,
                    'assigned_to': action.assigned_to,
                    'dependencies': action.dependencies,
                    'acceptance_criteria': action.acceptance_criteria
                }
                for action in report.improvement_plan
            ],
            'user_action_required': [
                {
                    'id': action.id,
                    'title': action.title,
                    'description': action.description,
                    'urgency': action.urgency.value,
                    'instructions': action.instructions,
                    'expected_outcome': action.expected_outcome
                }
                for action in report.user_action_required
            ]
        }
    
    def _create_emergency_report(self, error_message: str) -> ComprehensiveReport:
        """Create emergency report when test execution fails catastrophically."""
        emergency_issue = Issue(
            id=f"emergency_{int(datetime.utcnow().timestamp())}",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.FUNCTIONALITY,
            title="Test execution failed catastrophically",
            description=error_message,
            affected_components=["test_infrastructure"],
            reproduction_steps=["Run comprehensive test suite"],
            expected_behavior="Test suite should execute successfully",
            actual_behavior=f"Test execution failed: {error_message}",
            fix_priority=200,  # Highest priority
            estimated_effort="4-8 hours"
        )
        
        emergency_action = UserAction(
            id="emergency_action",
            title="Fix Test Infrastructure",
            description="Test infrastructure failed - immediate attention required",
            urgency=Urgency.IMMEDIATE,
            instructions=[
                "Review test orchestrator logs",
                "Check test environment setup",
                "Verify external service connectivity",
                "Fix infrastructure issues before retrying"
            ],
            expected_outcome="Test infrastructure is restored and functional"
        )
        
        return ComprehensiveReport(
            overall_status="INFRASTRUCTURE_FAILURE",
            total_execution_time=self.performance_metrics.get('total_execution_time', 0.0),
            suite_results=[],
            critical_issues=[emergency_issue],
            improvement_plan=[],
            user_action_required=[emergency_action]
        )
    
    async def _cleanup_test_environment(self):
        """Cleanup test environment."""
        self.logger.info("Cleaning up test environment")
        
        try:
            if self.test_environment:
                await self.test_environment.cleanup()
            
            if self.test_data_manager:
                await self.test_data_manager.cleanup()
            
            self.logger.info("Test environment cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")