"""
Test Result Collection System

Implements comprehensive test execution tracking, performance metrics collection,
and error categorization and analysis for the comprehensive testing framework.
"""
import asyncio
import logging
import time
import psutil
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import json
import os
import traceback

from tests.infrastructure.models import (
    TestResult, TestSuiteResult, TestStatus, PerformanceMetrics,
    IssueSeverity, IssueCategory
)


class MetricType(Enum):
    """Types of metrics to collect."""
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    RESOURCE_USAGE = "resource_usage"
    DATABASE_PERFORMANCE = "database_performance"
    EXTERNAL_API_PERFORMANCE = "external_api_performance"


class ErrorCategory(Enum):
    """Categories for error classification."""
    AUTHENTICATION_ERROR = "authentication_error"
    AUTHORIZATION_ERROR = "authorization_error"
    VALIDATION_ERROR = "validation_error"
    DATABASE_ERROR = "database_error"
    EXTERNAL_API_ERROR = "external_api_error"
    NETWORK_ERROR = "network_error"
    TIMEOUT_ERROR = "timeout_error"
    CONFIGURATION_ERROR = "configuration_error"
    BUSINESS_LOGIC_ERROR = "business_logic_error"
    INFRASTRUCTURE_ERROR = "infrastructure_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class MetricDataPoint:
    """Single metric data point."""
    timestamp: datetime
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorAnalysis:
    """Analysis of a specific error."""
    error_category: ErrorCategory
    error_message: str
    stack_trace: Optional[str]
    frequency: int
    first_occurrence: datetime
    last_occurrence: datetime
    affected_tests: List[str]
    potential_causes: List[str]
    suggested_fixes: List[str]


@dataclass
class PerformanceAnalysis:
    """Performance analysis for a test or component."""
    component_name: str
    avg_response_time: float
    p95_response_time: float
    p99_response_time: float
    throughput: float
    error_rate: float
    resource_usage: Dict[str, float]
    bottlenecks: List[str]
    recommendations: List[str]


class TestResultCollector:
    """
    Comprehensive test result collection system.
    
    Tracks test execution, collects performance metrics,
    and performs error categorization and analysis.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize test result collector."""
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        # Test execution tracking
        self.test_results: List[TestResult] = []
        self.suite_results: List[TestSuiteResult] = []
        self.current_test_context: Optional[Dict[str, Any]] = None
        
        # Performance metrics collection
        self.metrics: Dict[MetricType, List[MetricDataPoint]] = defaultdict(list)
        self.performance_baselines: Dict[str, float] = {}
        self.resource_monitor_active = False
        self.resource_monitor_thread: Optional[threading.Thread] = None
        
        # Error analysis
        self.error_patterns: Dict[str, ErrorAnalysis] = {}
        self.error_frequency: Dict[ErrorCategory, int] = defaultdict(int)
        
        # Real-time monitoring
        self.monitoring_active = False
        self.monitoring_interval = self.config.get('monitoring_interval', 1.0)  # seconds
        
        # Performance thresholds
        self.performance_thresholds = {
            'response_time_warning': self.config.get('response_time_warning', 2.0),  # seconds
            'response_time_critical': self.config.get('response_time_critical', 5.0),  # seconds
            'error_rate_warning': self.config.get('error_rate_warning', 0.05),  # 5%
            'error_rate_critical': self.config.get('error_rate_critical', 0.10),  # 10%
            'cpu_usage_warning': self.config.get('cpu_usage_warning', 80.0),  # percent
            'memory_usage_warning': self.config.get('memory_usage_warning', 80.0),  # percent
        }
    
    async def start_collection(self, test_context: Dict[str, Any]):
        """Start test result collection for a test session."""
        self.logger.info("Starting test result collection")
        self.current_test_context = test_context
        
        # Start resource monitoring
        await self._start_resource_monitoring()
        
        # Initialize performance baselines
        await self._initialize_performance_baselines()
        
        self.monitoring_active = True
        self.logger.info("Test result collection started successfully")
    
    async def stop_collection(self) -> Dict[str, Any]:
        """Stop test result collection and return summary."""
        self.logger.info("Stopping test result collection")
        self.monitoring_active = False
        
        # Stop resource monitoring
        await self._stop_resource_monitoring()
        
        # Generate collection summary
        summary = await self._generate_collection_summary()
        
        self.logger.info("Test result collection stopped")
        return summary
    
    def record_test_start(self, test_name: str, test_metadata: Optional[Dict[str, Any]] = None):
        """Record the start of a test execution."""
        self.logger.debug(f"Recording test start: {test_name}")
        
        # Update current test context
        if self.current_test_context:
            self.current_test_context.update({
                'current_test': test_name,
                'test_start_time': time.time(),
                'test_metadata': test_metadata or {}
            })
    
    def record_test_result(self, test_result: TestResult):
        """Record a completed test result with analysis."""
        self.logger.debug(f"Recording test result: {test_result.test_name} - {test_result.status.value}")
        
        # Store test result
        self.test_results.append(test_result)
        
        # Analyze test result for errors
        if test_result.status in [TestStatus.FAILED, TestStatus.ERROR]:
            self._analyze_test_error(test_result)
        
        # Record performance metrics
        self._record_test_performance_metrics(test_result)
        
        # Update current context
        if self.current_test_context:
            self.current_test_context['current_test'] = None
    
    def record_suite_result(self, suite_result: TestSuiteResult):
        """Record a completed test suite result."""
        self.logger.info(f"Recording suite result: {suite_result.suite_name}")
        
        # Store suite result
        self.suite_results.append(suite_result)
        
        # Analyze suite performance
        self._analyze_suite_performance(suite_result)
    
    def record_performance_metric(self, metric_type: MetricType, value: float, 
                                metadata: Optional[Dict[str, Any]] = None):
        """Record a performance metric data point."""
        data_point = MetricDataPoint(
            timestamp=datetime.utcnow(),
            value=value,
            metadata=metadata or {}
        )
        
        self.metrics[metric_type].append(data_point)
        
        # Check against thresholds
        self._check_performance_thresholds(metric_type, value)
    
    def record_api_call_metrics(self, endpoint: str, response_time: float, 
                              status_code: int, error: Optional[str] = None):
        """Record metrics for API call."""
        # Record response time
        self.record_performance_metric(
            MetricType.RESPONSE_TIME,
            response_time,
            {'endpoint': endpoint, 'status_code': status_code}
        )
        
        # Record error if present
        if error or status_code >= 400:
            self.record_performance_metric(
                MetricType.ERROR_RATE,
                1.0,
                {'endpoint': endpoint, 'status_code': status_code, 'error': error}
            )
    
    def record_database_metrics(self, operation: str, execution_time: float, 
                              rows_affected: Optional[int] = None):
        """Record database operation metrics."""
        self.record_performance_metric(
            MetricType.DATABASE_PERFORMANCE,
            execution_time,
            {'operation': operation, 'rows_affected': rows_affected}
        )
    
    def record_external_api_metrics(self, service: str, operation: str, 
                                  response_time: float, success: bool):
        """Record external API call metrics."""
        self.record_performance_metric(
            MetricType.EXTERNAL_API_PERFORMANCE,
            response_time,
            {'service': service, 'operation': operation, 'success': success}
        )
    
    async def get_performance_analysis(self, component: Optional[str] = None) -> List[PerformanceAnalysis]:
        """Get performance analysis for components."""
        analyses = []
        
        if component:
            analysis = await self._analyze_component_performance(component)
            if analysis:
                analyses.append(analysis)
        else:
            # Analyze all components
            components = self._identify_components()
            for comp in components:
                analysis = await self._analyze_component_performance(comp)
                if analysis:
                    analyses.append(analysis)
        
        return analyses
    
    async def get_error_analysis(self) -> List[ErrorAnalysis]:
        """Get comprehensive error analysis."""
        return list(self.error_patterns.values())
    
    async def get_test_execution_summary(self) -> Dict[str, Any]:
        """Get summary of test execution."""
        total_tests = len(self.test_results)
        if total_tests == 0:
            return {'message': 'No tests executed'}
        
        # Calculate status distribution
        status_counts = defaultdict(int)
        total_execution_time = 0.0
        
        for result in self.test_results:
            status_counts[result.status.value] += 1
            total_execution_time += result.execution_time
        
        # Calculate suite statistics
        suite_stats = {}
        for suite in self.suite_results:
            suite_stats[suite.suite_name] = {
                'total_tests': suite.total_tests,
                'passed': suite.passed,
                'failed': suite.failed,
                'errors': suite.errors,
                'execution_time': suite.execution_time,
                'success_rate': (suite.passed / suite.total_tests) * 100 if suite.total_tests > 0 else 0
            }
        
        return {
            'total_tests': total_tests,
            'status_distribution': dict(status_counts),
            'total_execution_time': total_execution_time,
            'average_test_time': total_execution_time / total_tests,
            'suite_statistics': suite_stats,
            'overall_success_rate': (status_counts['passed'] / total_tests) * 100,
            'error_categories': dict(self.error_frequency)
        }
    
    def _analyze_test_error(self, test_result: TestResult):
        """Analyze test error and categorize it."""
        if not test_result.error_message:
            return
        
        # Categorize error
        error_category = self._categorize_error(test_result.error_message, test_result.details)
        
        # Update error frequency
        self.error_frequency[error_category] += 1
        
        # Create or update error pattern
        error_key = f"{error_category.value}_{hash(test_result.error_message) % 10000}"
        
        if error_key in self.error_patterns:
            # Update existing pattern
            pattern = self.error_patterns[error_key]
            pattern.frequency += 1
            pattern.last_occurrence = test_result.timestamp
            pattern.affected_tests.append(test_result.test_name)
        else:
            # Create new pattern
            self.error_patterns[error_key] = ErrorAnalysis(
                error_category=error_category,
                error_message=test_result.error_message,
                stack_trace=test_result.details.get('exception'),
                frequency=1,
                first_occurrence=test_result.timestamp,
                last_occurrence=test_result.timestamp,
                affected_tests=[test_result.test_name],
                potential_causes=self._identify_potential_causes(error_category, test_result.error_message),
                suggested_fixes=self._suggest_fixes(error_category, test_result.error_message)
            )
    
    def _categorize_error(self, error_message: str, details: Dict[str, Any]) -> ErrorCategory:
        """Categorize error based on message and details."""
        error_lower = error_message.lower()
        
        # Authentication errors
        if any(keyword in error_lower for keyword in ['unauthorized', 'authentication', 'login', 'token']):
            return ErrorCategory.AUTHENTICATION_ERROR
        
        # Authorization errors
        if any(keyword in error_lower for keyword in ['forbidden', 'permission', 'access denied', 'authorization']):
            return ErrorCategory.AUTHORIZATION_ERROR
        
        # Validation errors
        if any(keyword in error_lower for keyword in ['validation', 'invalid', 'required field', 'format']):
            return ErrorCategory.VALIDATION_ERROR
        
        # Database errors
        if any(keyword in error_lower for keyword in ['database', 'sql', 'connection', 'constraint', 'integrity']):
            return ErrorCategory.DATABASE_ERROR
        
        # External API errors
        if any(keyword in error_lower for keyword in ['api', 'http', 'request', 'response', 'service']):
            return ErrorCategory.EXTERNAL_API_ERROR
        
        # Network errors
        if any(keyword in error_lower for keyword in ['network', 'connection', 'timeout', 'unreachable']):
            return ErrorCategory.NETWORK_ERROR
        
        # Timeout errors
        if any(keyword in error_lower for keyword in ['timeout', 'timed out', 'deadline']):
            return ErrorCategory.TIMEOUT_ERROR
        
        # Configuration errors
        if any(keyword in error_lower for keyword in ['config', 'environment', 'missing', 'not found']):
            return ErrorCategory.CONFIGURATION_ERROR
        
        # Business logic errors
        if any(keyword in error_lower for keyword in ['business', 'logic', 'rule', 'workflow']):
            return ErrorCategory.BUSINESS_LOGIC_ERROR
        
        # Infrastructure errors
        if any(keyword in error_lower for keyword in ['infrastructure', 'server', 'service', 'deployment']):
            return ErrorCategory.INFRASTRUCTURE_ERROR
        
        return ErrorCategory.UNKNOWN_ERROR
    
    def _identify_potential_causes(self, category: ErrorCategory, error_message: str) -> List[str]:
        """Identify potential causes for an error category."""
        causes_map = {
            ErrorCategory.AUTHENTICATION_ERROR: [
                "Invalid credentials",
                "Expired authentication token",
                "Missing authentication headers",
                "Authentication service unavailable"
            ],
            ErrorCategory.AUTHORIZATION_ERROR: [
                "Insufficient user permissions",
                "Role-based access control misconfiguration",
                "Resource access restrictions",
                "Tenant isolation issues"
            ],
            ErrorCategory.VALIDATION_ERROR: [
                "Invalid input data format",
                "Missing required fields",
                "Data type mismatch",
                "Business rule violations"
            ],
            ErrorCategory.DATABASE_ERROR: [
                "Database connection issues",
                "SQL constraint violations",
                "Database schema mismatch",
                "Transaction conflicts"
            ],
            ErrorCategory.EXTERNAL_API_ERROR: [
                "External service unavailable",
                "API rate limiting",
                "Invalid API credentials",
                "API response format changes"
            ],
            ErrorCategory.NETWORK_ERROR: [
                "Network connectivity issues",
                "DNS resolution problems",
                "Firewall blocking requests",
                "Service endpoint unreachable"
            ],
            ErrorCategory.TIMEOUT_ERROR: [
                "Slow database queries",
                "External service delays",
                "Network latency issues",
                "Resource contention"
            ],
            ErrorCategory.CONFIGURATION_ERROR: [
                "Missing environment variables",
                "Incorrect configuration values",
                "Service misconfiguration",
                "Deployment configuration issues"
            ]
        }
        
        return causes_map.get(category, ["Unknown cause"])
    
    def _suggest_fixes(self, category: ErrorCategory, error_message: str) -> List[str]:
        """Suggest fixes for an error category."""
        fixes_map = {
            ErrorCategory.AUTHENTICATION_ERROR: [
                "Verify authentication credentials",
                "Check token expiration and refresh logic",
                "Validate authentication service configuration",
                "Review authentication middleware"
            ],
            ErrorCategory.AUTHORIZATION_ERROR: [
                "Review user role assignments",
                "Check permission configurations",
                "Validate access control rules",
                "Test tenant isolation"
            ],
            ErrorCategory.VALIDATION_ERROR: [
                "Review input validation rules",
                "Check data format requirements",
                "Validate business logic constraints",
                "Update validation schemas"
            ],
            ErrorCategory.DATABASE_ERROR: [
                "Check database connectivity",
                "Review database schema",
                "Optimize database queries",
                "Check transaction handling"
            ],
            ErrorCategory.EXTERNAL_API_ERROR: [
                "Verify external service status",
                "Check API credentials and permissions",
                "Review rate limiting configuration",
                "Implement retry mechanisms"
            ],
            ErrorCategory.NETWORK_ERROR: [
                "Check network connectivity",
                "Verify DNS configuration",
                "Review firewall rules",
                "Test service endpoints"
            ],
            ErrorCategory.TIMEOUT_ERROR: [
                "Optimize slow operations",
                "Increase timeout values",
                "Implement async processing",
                "Add performance monitoring"
            ],
            ErrorCategory.CONFIGURATION_ERROR: [
                "Verify environment variables",
                "Check configuration files",
                "Review service settings",
                "Validate deployment configuration"
            ]
        }
        
        return fixes_map.get(category, ["Review error details and logs"])
    
    def _record_test_performance_metrics(self, test_result: TestResult):
        """Record performance metrics for a test result."""
        # Record execution time
        self.record_performance_metric(
            MetricType.RESPONSE_TIME,
            test_result.execution_time,
            {'test_name': test_result.test_name, 'status': test_result.status.value}
        )
        
        # Record error rate
        error_value = 1.0 if test_result.status in [TestStatus.FAILED, TestStatus.ERROR] else 0.0
        self.record_performance_metric(
            MetricType.ERROR_RATE,
            error_value,
            {'test_name': test_result.test_name}
        )
    
    def _analyze_suite_performance(self, suite_result: TestSuiteResult):
        """Analyze performance of a test suite."""
        # Calculate suite-level metrics
        if suite_result.total_tests > 0:
            suite_error_rate = (suite_result.failed + suite_result.errors) / suite_result.total_tests
            avg_test_time = suite_result.execution_time / suite_result.total_tests
            
            # Record suite metrics
            self.record_performance_metric(
                MetricType.ERROR_RATE,
                suite_error_rate,
                {'suite_name': suite_result.suite_name, 'type': 'suite_level'}
            )
            
            self.record_performance_metric(
                MetricType.RESPONSE_TIME,
                avg_test_time,
                {'suite_name': suite_result.suite_name, 'type': 'average_test_time'}
            )
    
    async def _start_resource_monitoring(self):
        """Start resource monitoring in background thread."""
        if self.resource_monitor_active:
            return
        
        self.resource_monitor_active = True
        self.resource_monitor_thread = threading.Thread(
            target=self._resource_monitor_loop,
            daemon=True
        )
        self.resource_monitor_thread.start()
        self.logger.info("Resource monitoring started")
    
    async def _stop_resource_monitoring(self):
        """Stop resource monitoring."""
        self.resource_monitor_active = False
        if self.resource_monitor_thread:
            self.resource_monitor_thread.join(timeout=5.0)
        self.logger.info("Resource monitoring stopped")
    
    def _resource_monitor_loop(self):
        """Resource monitoring loop (runs in background thread)."""
        while self.resource_monitor_active:
            try:
                # Collect system metrics
                cpu_percent = psutil.cpu_percent(interval=None)
                memory = psutil.virtual_memory()
                
                # Record metrics
                self.record_performance_metric(
                    MetricType.RESOURCE_USAGE,
                    cpu_percent,
                    {'resource': 'cpu', 'unit': 'percent'}
                )
                
                self.record_performance_metric(
                    MetricType.RESOURCE_USAGE,
                    memory.percent,
                    {'resource': 'memory', 'unit': 'percent'}
                )
                
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {str(e)}")
                time.sleep(self.monitoring_interval)
    
    def _check_performance_thresholds(self, metric_type: MetricType, value: float):
        """Check if metric value exceeds performance thresholds."""
        if metric_type == MetricType.RESPONSE_TIME:
            if value > self.performance_thresholds['response_time_critical']:
                self.logger.warning(f"Critical response time detected: {value:.2f}s")
            elif value > self.performance_thresholds['response_time_warning']:
                self.logger.warning(f"Slow response time detected: {value:.2f}s")
        
        elif metric_type == MetricType.ERROR_RATE:
            if value > self.performance_thresholds['error_rate_critical']:
                self.logger.warning(f"Critical error rate detected: {value:.2%}")
            elif value > self.performance_thresholds['error_rate_warning']:
                self.logger.warning(f"High error rate detected: {value:.2%}")
    
    async def _initialize_performance_baselines(self):
        """Initialize performance baselines for comparison."""
        # Load historical baselines if available
        baseline_file = "test_performance_baselines.json"
        if os.path.exists(baseline_file):
            try:
                with open(baseline_file, 'r') as f:
                    self.performance_baselines = json.load(f)
                self.logger.info("Loaded performance baselines")
            except Exception as e:
                self.logger.warning(f"Failed to load performance baselines: {str(e)}")
    
    async def _generate_collection_summary(self) -> Dict[str, Any]:
        """Generate summary of collection session."""
        return {
            'collection_duration': time.time() - self.current_test_context.get('collection_start_time', time.time()),
            'total_tests_recorded': len(self.test_results),
            'total_suites_recorded': len(self.suite_results),
            'total_metrics_collected': sum(len(metrics) for metrics in self.metrics.values()),
            'error_patterns_identified': len(self.error_patterns),
            'performance_issues_detected': self._count_performance_issues(),
            'resource_monitoring_active': self.resource_monitor_active
        }
    
    def _count_performance_issues(self) -> int:
        """Count detected performance issues."""
        issues = 0
        
        # Count response time issues
        response_times = self.metrics.get(MetricType.RESPONSE_TIME, [])
        for metric in response_times:
            if metric.value > self.performance_thresholds['response_time_warning']:
                issues += 1
        
        # Count error rate issues
        error_rates = self.metrics.get(MetricType.ERROR_RATE, [])
        for metric in error_rates:
            if metric.value > self.performance_thresholds['error_rate_warning']:
                issues += 1
        
        return issues
    
    def _identify_components(self) -> List[str]:
        """Identify components from collected metrics."""
        components = set()
        
        for metric_list in self.metrics.values():
            for metric in metric_list:
                if 'component' in metric.metadata:
                    components.add(metric.metadata['component'])
                elif 'suite_name' in metric.metadata:
                    components.add(metric.metadata['suite_name'])
                elif 'endpoint' in metric.metadata:
                    components.add(metric.metadata['endpoint'])
        
        return list(components)
    
    async def _analyze_component_performance(self, component: str) -> Optional[PerformanceAnalysis]:
        """Analyze performance for a specific component."""
        # Collect metrics for this component
        component_metrics = []
        
        for metric_type, metric_list in self.metrics.items():
            for metric in metric_list:
                if (metric.metadata.get('component') == component or
                    metric.metadata.get('suite_name') == component or
                    metric.metadata.get('endpoint') == component):
                    component_metrics.append((metric_type, metric))
        
        if not component_metrics:
            return None
        
        # Calculate performance statistics
        response_times = [m.value for mt, m in component_metrics if mt == MetricType.RESPONSE_TIME]
        error_rates = [m.value for mt, m in component_metrics if mt == MetricType.ERROR_RATE]
        
        if not response_times:
            return None
        
        # Calculate statistics
        avg_response_time = sum(response_times) / len(response_times)
        sorted_times = sorted(response_times)
        p95_response_time = sorted_times[int(len(sorted_times) * 0.95)] if sorted_times else 0
        p99_response_time = sorted_times[int(len(sorted_times) * 0.99)] if sorted_times else 0
        
        error_rate = sum(error_rates) / len(error_rates) if error_rates else 0
        throughput = len(response_times) / max(1, max(response_times) - min(response_times)) if len(response_times) > 1 else 0
        
        # Identify bottlenecks and recommendations
        bottlenecks = []
        recommendations = []
        
        if avg_response_time > self.performance_thresholds['response_time_warning']:
            bottlenecks.append("Slow response times")
            recommendations.append("Optimize component performance")
        
        if error_rate > self.performance_thresholds['error_rate_warning']:
            bottlenecks.append("High error rate")
            recommendations.append("Investigate and fix error causes")
        
        return PerformanceAnalysis(
            component_name=component,
            avg_response_time=avg_response_time,
            p95_response_time=p95_response_time,
            p99_response_time=p99_response_time,
            throughput=throughput,
            error_rate=error_rate,
            resource_usage={},  # Would be populated with component-specific resource usage
            bottlenecks=bottlenecks,
            recommendations=recommendations
        )