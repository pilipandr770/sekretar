"""
Data models for comprehensive testing infrastructure.

Defines all data structures used in the testing framework.
"""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class TestStatus(Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"


class IssueSeverity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueCategory(Enum):
    """Issue categories."""
    FUNCTIONALITY = "functionality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    USABILITY = "usability"


class Priority(Enum):
    """Priority levels."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Urgency(Enum):
    """Urgency levels for user actions."""
    IMMEDIATE = "immediate"
    SOON = "soon"
    WHEN_CONVENIENT = "when_convenient"


@dataclass
class TestResult:
    """Result of a single test execution."""
    test_name: str
    status: TestStatus
    execution_time: float
    error_message: Optional[str]
    details: Dict[str, Any]
    timestamp: datetime


@dataclass
class TestSuiteResult:
    """Result of a test suite execution."""
    suite_name: str
    total_tests: int
    passed: int
    failed: int
    skipped: int
    errors: int
    execution_time: float
    test_results: List[TestResult]


@dataclass
class Issue:
    """Detected issue from test execution."""
    id: str
    severity: IssueSeverity
    category: IssueCategory
    title: str
    description: str
    affected_components: List[str]
    reproduction_steps: List[str]
    expected_behavior: str
    actual_behavior: str
    fix_priority: int
    estimated_effort: str


@dataclass
class ActionItem:
    """Action item for improvement plan."""
    id: str
    title: str
    description: str
    priority: Priority
    estimated_time: str
    assigned_to: str
    dependencies: List[str]
    acceptance_criteria: List[str]


@dataclass
class UserAction:
    """Action required from user."""
    id: str
    title: str
    description: str
    urgency: Urgency
    instructions: List[str]
    expected_outcome: str


@dataclass
class ComprehensiveReport:
    """Comprehensive test execution report."""
    overall_status: str
    total_execution_time: float
    suite_results: List[TestSuiteResult]
    critical_issues: List[Issue]
    improvement_plan: List[ActionItem]
    user_action_required: List[UserAction]


@dataclass
class CompanyData:
    """Real company data structure."""
    name: str
    vat_number: Optional[str]
    lei_code: Optional[str]
    country_code: str
    address: Optional[str]
    industry: Optional[str]
    size: Optional[str]  # SME, Large, etc.
    source: str  # Data source identifier
    validation_status: str  # VALID, INVALID, PENDING
    last_validated: Optional[datetime] = None
    additional_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TestEnvironmentConfig:
    """Test environment configuration."""
    database_url: str
    redis_url: str
    api_base_url: str
    external_services: Dict[str, str]
    test_data_path: str
    cleanup_on_exit: bool = True
    parallel_execution: bool = False
    max_workers: int = 4


@dataclass
class DataSourceConfig:
    """Configuration for external data sources."""
    vies_api_url: str
    gleif_api_url: str
    companies_house_api_key: Optional[str]
    opencorporates_api_key: Optional[str]
    rate_limits: Dict[str, int]  # requests per minute for each service
    timeout_seconds: int = 30
    retry_attempts: int = 3


@dataclass
class PerformanceMetrics:
    """Performance metrics for test execution."""
    response_times: List[float]
    throughput: float  # requests per second
    error_rate: float
    cpu_usage: float
    memory_usage: float
    database_connections: int
    redis_connections: int


@dataclass
class SecurityTestResult:
    """Security test specific result."""
    test_name: str
    vulnerability_type: str
    risk_level: str  # HIGH, MEDIUM, LOW
    description: str
    remediation_steps: List[str]
    cve_references: List[str] = field(default_factory=list)


@dataclass
class IntegrationTestContext:
    """Context for integration tests."""
    external_services_status: Dict[str, bool]
    mock_services: Dict[str, Any]
    test_data_sets: Dict[str, List[CompanyData]]
    authentication_tokens: Dict[str, str]
    tenant_contexts: List[Dict[str, Any]]