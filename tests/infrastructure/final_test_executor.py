"""
Final Test Execution System

Implements comprehensive test suite execution with detailed logging,
performance metrics collection, and comprehensive reporting.
"""
import asyncio
import logging
import time
import sys
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
import traceback

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tests.infrastructure.test_orchestrator import TestOrchestrator, TestCategory
from tests.infrastructure.test_result_collector import TestResultCollector
from tests.infrastructure.models import ComprehensiveReport
from tests.infrastructure.test_environment import TestEnvironment
from tests.infrastructure.test_data_manager import TestDataManager


class FinalTestExecutor:
    """
    Final test execution system that runs all test categories in proper sequence,
    collects comprehensive performance and error metrics, and generates detailed
    execution logs and traces.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize final test executor."""
        self.config = config or {}
        self.logger = self._setup_logging()
        
        # Initialize components
        self.orchestrator = TestOrchestrator(self.config.get('orchestrator', {}))
        self.result_collector = TestResultCollector(self.config.get('result_collector', {}))
        
        # Execution tracking
        self.execution_start_time: Optional[datetime] = None
        self.execution_logs: List[Dict[str, Any]] = []
        self.performance_traces: List[Dict[str, Any]] = []
        
        # Test suite registry
        self._register_all_test_suites()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup comprehensive logging for test execution."""
        logger = logging.getLogger('final_test_executor')
        logger.setLevel(logging.DEBUG)
        
        # Create logs directory
        logs_dir = Path("test_execution_logs")
        logs_dir.mkdir(exist_ok=True)
        
        # Create timestamp for this execution
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # File handler for detailed logs
        file_handler = logging.FileHandler(
            logs_dir / f"test_execution_{timestamp}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        
        # Console handler for real-time feedback
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def _register_all_test_suites(self):
        """Register all available test suites with the orchestrator."""
        self.logger.info("Registering all test suites")
        
        # Import and register test functions for each category
        test_suite_mappings = {
            TestCategory.USER_REGISTRATION: self._get_user_registration_tests(),
            TestCategory.API_ENDPOINTS: self._get_api_endpoint_tests(),
            TestCategory.CRM_FUNCTIONALITY: self._get_crm_functionality_tests(),
            TestCategory.KYB_MONITORING: self._get_kyb_monitoring_tests(),
            TestCategory.AI_AGENTS: self._get_ai_agent_tests(),
            TestCategory.BILLING: self._get_billing_tests(),
            TestCategory.CALENDAR: self._get_calendar_tests(),
            TestCategory.KNOWLEDGE: self._get_knowledge_tests(),
            TestCategory.COMMUNICATION: self._get_communication_tests(),
            TestCategory.INTEGRATION: self._get_integration_tests(),
            TestCategory.PERFORMANCE: self._get_performance_tests(),
            TestCategory.SECURITY: self._get_security_tests()
        }
        
        for category, test_functions in test_suite_mappings.items():
            if test_functions:
                self.orchestrator.register_test_suite(category, test_functions)
        
        self.logger.info(f"Registered {len(test_suite_mappings)} test categories")
    
    async def execute_complete_test_suite(self) -> ComprehensiveReport:
        """
        Execute the complete test suite in proper sequence with comprehensive
        performance and error metrics collection.
        
        Returns:
            ComprehensiveReport: Detailed report with all findings
        """
        self.execution_start_time = datetime.utcnow()
        self.logger.info("=" * 80)
        self.logger.info("STARTING COMPREHENSIVE TEST SUITE EXECUTION")
        self.logger.info("=" * 80)
        
        try:
            # Phase 1: Pre-execution setup
            await self._pre_execution_setup()
            
            # Phase 2: Start result collection
            await self._start_result_collection()
            
            # Phase 3: Execute test suite
            report = await self._execute_test_suite_with_monitoring()
            
            # Phase 4: Post-execution analysis
            await self._post_execution_analysis(report)
            
            # Phase 5: Generate execution traces
            await self._generate_execution_traces()
            
            self.logger.info("=" * 80)
            self.logger.info("COMPREHENSIVE TEST SUITE EXECUTION COMPLETED")
            self.logger.info("=" * 80)
            
            return report
            
        except Exception as e:
            self.logger.error(f"Critical error during test execution: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Create emergency report
            return await self._create_emergency_report(str(e))
            
        finally:
            # Cleanup
            await self._cleanup_execution()
    
    async def _pre_execution_setup(self):
        """Setup phase before test execution."""
        self.logger.info("Phase 1: Pre-execution setup")
        
        # Log system information
        await self._log_system_information()
        
        # Validate test environment
        await self._validate_test_environment()
        
        # Initialize performance baselines
        await self._initialize_performance_baselines()
        
        self.logger.info("Pre-execution setup completed")
    
    async def _start_result_collection(self):
        """Start comprehensive result collection."""
        self.logger.info("Phase 2: Starting result collection")
        
        test_context = {
            'execution_id': f"exec_{int(self.execution_start_time.timestamp())}",
            'start_time': self.execution_start_time,
            'collection_start_time': time.time()
        }
        
        await self.result_collector.start_collection(test_context)
        self.logger.info("Result collection started")
    
    async def _execute_test_suite_with_monitoring(self) -> ComprehensiveReport:
        """Execute test suite with comprehensive monitoring."""
        self.logger.info("Phase 3: Executing test suite with monitoring")
        
        # Start execution monitoring
        monitoring_task = asyncio.create_task(self._monitor_execution())
        
        try:
            # Execute comprehensive test suite
            report = await self.orchestrator.run_comprehensive_test_suite()
            
            # Log execution summary
            await self._log_execution_summary(report)
            
            return report
            
        finally:
            # Stop monitoring
            monitoring_task.cancel()
            try:
                await monitoring_task
            except asyncio.CancelledError:
                pass
    
    async def _post_execution_analysis(self, report: ComprehensiveReport):
        """Perform post-execution analysis."""
        self.logger.info("Phase 4: Post-execution analysis")
        
        # Stop result collection and get summary
        collection_summary = await self.result_collector.stop_collection()
        self.logger.info(f"Collection summary: {collection_summary}")
        
        # Get performance analysis
        performance_analyses = await self.result_collector.get_performance_analysis()
        self.logger.info(f"Generated {len(performance_analyses)} performance analyses")
        
        # Get error analysis
        error_analyses = await self.result_collector.get_error_analysis()
        self.logger.info(f"Identified {len(error_analyses)} error patterns")
        
        # Log critical findings
        await self._log_critical_findings(report, performance_analyses, error_analyses)
    
    async def _generate_execution_traces(self):
        """Generate detailed execution logs and traces."""
        self.logger.info("Phase 5: Generating execution traces")
        
        # Create traces directory
        traces_dir = Path("test_execution_traces")
        traces_dir.mkdir(exist_ok=True)
        
        timestamp = self.execution_start_time.strftime("%Y%m%d_%H%M%S")
        
        # Generate execution trace file
        trace_file = traces_dir / f"execution_trace_{timestamp}.json"
        
        execution_trace = {
            'execution_id': f"exec_{int(self.execution_start_time.timestamp())}",
            'start_time': self.execution_start_time.isoformat(),
            'end_time': datetime.utcnow().isoformat(),
            'total_duration': (datetime.utcnow() - self.execution_start_time).total_seconds(),
            'execution_logs': self.execution_logs,
            'performance_traces': self.performance_traces,
            'system_info': await self._get_system_info(),
            'environment_info': await self._get_environment_info()
        }
        
        with open(trace_file, 'w') as f:
            json.dump(execution_trace, f, indent=2, default=str)
        
        self.logger.info(f"Execution trace saved to {trace_file}")
    
    async def _monitor_execution(self):
        """Monitor test execution in real-time."""
        while True:
            try:
                # Collect current execution metrics
                current_time = datetime.utcnow()
                
                # Log execution progress
                execution_log = {
                    'timestamp': current_time.isoformat(),
                    'elapsed_time': (current_time - self.execution_start_time).total_seconds(),
                    'current_phase': 'test_execution',
                    'memory_usage': await self._get_memory_usage(),
                    'cpu_usage': await self._get_cpu_usage()
                }
                
                self.execution_logs.append(execution_log)
                
                # Create performance trace
                performance_trace = {
                    'timestamp': current_time.isoformat(),
                    'metrics': await self._collect_current_metrics()
                }
                
                self.performance_traces.append(performance_trace)
                
                # Wait before next monitoring cycle
                await asyncio.sleep(5.0)  # Monitor every 5 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in execution monitoring: {str(e)}")
                await asyncio.sleep(5.0)
    
    async def _log_system_information(self):
        """Log comprehensive system information."""
        self.logger.info("System Information:")
        self.logger.info(f"  Python version: {sys.version}")
        self.logger.info(f"  Platform: {sys.platform}")
        self.logger.info(f"  Working directory: {os.getcwd()}")
        self.logger.info(f"  Execution start time: {self.execution_start_time}")
        
        # Log environment variables (non-sensitive)
        env_vars = {k: v for k, v in os.environ.items() 
                   if not any(sensitive in k.lower() for sensitive in ['password', 'secret', 'key', 'token'])}
        self.logger.debug(f"Environment variables: {env_vars}")
    
    async def _validate_test_environment(self):
        """Validate test environment is ready."""
        self.logger.info("Validating test environment...")
        
        # Check required directories
        required_dirs = ['tests', 'tests/infrastructure', 'app']
        for dir_path in required_dirs:
            if not Path(dir_path).exists():
                raise RuntimeError(f"Required directory not found: {dir_path}")
        
        # Check required files
        required_files = ['requirements.txt', 'config.py']
        for file_path in required_files:
            if not Path(file_path).exists():
                self.logger.warning(f"Expected file not found: {file_path}")
        
        self.logger.info("Test environment validation completed")
    
    async def _initialize_performance_baselines(self):
        """Initialize performance baselines for comparison."""
        self.logger.info("Initializing performance baselines...")
        
        # Load existing baselines if available
        baseline_file = Path("test_performance_baselines.json")
        if baseline_file.exists():
            try:
                with open(baseline_file, 'r') as f:
                    baselines = json.load(f)
                self.logger.info(f"Loaded {len(baselines)} performance baselines")
            except Exception as e:
                self.logger.warning(f"Failed to load performance baselines: {str(e)}")
        else:
            self.logger.info("No existing performance baselines found")
    
    async def _log_execution_summary(self, report: ComprehensiveReport):
        """Log comprehensive execution summary."""
        self.logger.info("=" * 60)
        self.logger.info("EXECUTION SUMMARY")
        self.logger.info("=" * 60)
        
        self.logger.info(f"Overall Status: {report.overall_status}")
        self.logger.info(f"Total Execution Time: {report.total_execution_time:.2f} seconds")
        self.logger.info(f"Test Suites Executed: {len(report.suite_results)}")
        
        # Log suite results
        total_tests = sum(suite.total_tests for suite in report.suite_results)
        total_passed = sum(suite.passed for suite in report.suite_results)
        total_failed = sum(suite.failed for suite in report.suite_results)
        total_errors = sum(suite.errors for suite in report.suite_results)
        
        self.logger.info(f"Total Tests: {total_tests}")
        self.logger.info(f"Passed: {total_passed} ({(total_passed/total_tests)*100:.1f}%)")
        self.logger.info(f"Failed: {total_failed} ({(total_failed/total_tests)*100:.1f}%)")
        self.logger.info(f"Errors: {total_errors} ({(total_errors/total_tests)*100:.1f}%)")
        
        # Log critical issues
        self.logger.info(f"Critical Issues Detected: {len(report.critical_issues)}")
        self.logger.info(f"Improvement Actions: {len(report.improvement_plan)}")
        self.logger.info(f"User Actions Required: {len(report.user_action_required)}")
        
        self.logger.info("=" * 60)
    
    async def _log_critical_findings(self, report: ComprehensiveReport, 
                                   performance_analyses: List, error_analyses: List):
        """Log critical findings from execution."""
        self.logger.info("CRITICAL FINDINGS:")
        
        # Log critical issues
        critical_issues = [issue for issue in report.critical_issues 
                          if issue.severity.value == 'critical']
        
        if critical_issues:
            self.logger.warning(f"Found {len(critical_issues)} CRITICAL issues:")
            for issue in critical_issues[:5]:  # Log top 5
                self.logger.warning(f"  - {issue.title}: {issue.description}")
        
        # Log performance issues
        perf_issues = [analysis for analysis in performance_analyses 
                      if analysis.bottlenecks]
        
        if perf_issues:
            self.logger.warning(f"Found {len(perf_issues)} performance issues:")
            for analysis in perf_issues[:3]:  # Log top 3
                self.logger.warning(f"  - {analysis.component_name}: {', '.join(analysis.bottlenecks)}")
        
        # Log error patterns
        if error_analyses:
            self.logger.warning(f"Identified {len(error_analyses)} error patterns:")
            for error in error_analyses[:3]:  # Log top 3
                self.logger.warning(f"  - {error.error_category.value}: {error.frequency} occurrences")
    
    async def _create_emergency_report(self, error_message: str) -> ComprehensiveReport:
        """Create emergency report when execution fails."""
        from tests.infrastructure.models import Issue, UserAction, IssueSeverity, IssueCategory, Urgency
        
        emergency_issue = Issue(
            id=f"emergency_{int(datetime.utcnow().timestamp())}",
            severity=IssueSeverity.CRITICAL,
            category=IssueCategory.INFRASTRUCTURE,
            title="Test execution failed catastrophically",
            description=error_message,
            affected_components=["test_infrastructure"],
            reproduction_steps=["Run final test executor"],
            expected_behavior="Test execution should complete successfully",
            actual_behavior=f"Execution failed: {error_message}",
            fix_priority=200,
            estimated_effort="4-8 hours"
        )
        
        emergency_action = UserAction(
            id="emergency_action",
            title="Fix Test Execution Infrastructure",
            description="Test execution failed - immediate attention required",
            urgency=Urgency.IMMEDIATE,
            instructions=[
                "Review test execution logs",
                "Check system requirements",
                "Verify test environment setup",
                "Fix infrastructure issues"
            ],
            expected_outcome="Test execution infrastructure is restored"
        )
        
        return ComprehensiveReport(
            overall_status="EXECUTION_FAILURE",
            total_execution_time=0.0,
            suite_results=[],
            critical_issues=[emergency_issue],
            improvement_plan=[],
            user_action_required=[emergency_action]
        )
    
    async def _cleanup_execution(self):
        """Cleanup after test execution."""
        self.logger.info("Performing execution cleanup...")
        
        try:
            # Stop any remaining monitoring
            if hasattr(self, 'result_collector'):
                await self.result_collector.stop_collection()
            
            # Log final execution time
            if self.execution_start_time:
                total_time = (datetime.utcnow() - self.execution_start_time).total_seconds()
                self.logger.info(f"Total execution time: {total_time:.2f} seconds")
            
            self.logger.info("Execution cleanup completed")
            
        except Exception as e:
            self.logger.error(f"Error during cleanup: {str(e)}")
    
    # Helper methods for getting test functions
    def _get_user_registration_tests(self) -> List:
        """Get user registration test functions."""
        # Import actual test functions from test files
        test_functions = []
        
        try:
            # Try to import comprehensive user registration tests
            from tests.test_user_registration_comprehensive import (
                test_complete_registration_flow,
                test_email_validation_and_confirmation,
                test_company_data_validation,
                test_trial_activation
            )
            
            test_functions.extend([
                test_complete_registration_flow,
                test_email_validation_and_confirmation,
                test_company_data_validation,
                test_trial_activation
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import user registration tests: {str(e)}")
            # Use stub functions as fallback
            try:
                from tests.test_functions_stubs import (
                    test_complete_registration_flow,
                    test_email_validation_and_confirmation,
                    test_company_data_validation,
                    test_trial_activation
                )
                
                test_functions.extend([
                    test_complete_registration_flow,
                    test_email_validation_and_confirmation,
                    test_company_data_validation,
                    test_trial_activation
                ])
                
            except ImportError:
                self.logger.error("Could not import user registration test stubs")
        
        return test_functions
    
    def _get_api_endpoint_tests(self) -> List:
        """Get API endpoint test functions."""
        test_functions = []
        
        try:
            from tests.test_comprehensive_auth_api import (
                test_login_endpoint,
                test_token_refresh,
                test_oauth_callback
            )
            
            from tests.test_comprehensive_core_api import (
                test_tenant_endpoints,
                test_crm_endpoints,
                test_kyb_endpoints
            )
            
            test_functions.extend([
                test_login_endpoint,
                test_token_refresh,
                test_oauth_callback,
                test_tenant_endpoints,
                test_crm_endpoints,
                test_kyb_endpoints
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import API endpoint tests: {str(e)}")
        
        return test_functions
    
    def _get_crm_functionality_tests(self) -> List:
        """Get CRM functionality test functions."""
        test_functions = []
        
        try:
            from tests.test_crm_contact_management_comprehensive import (
                test_contact_creation,
                test_contact_search,
                test_contact_deduplication
            )
            
            from tests.test_lead_pipeline_management import (
                test_lead_creation,
                test_pipeline_progression,
                test_conversion_tracking
            )
            
            test_functions.extend([
                test_contact_creation,
                test_contact_search,
                test_contact_deduplication,
                test_lead_creation,
                test_pipeline_progression,
                test_conversion_tracking
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import CRM functionality tests: {str(e)}")
        
        return test_functions
    
    def _get_kyb_monitoring_tests(self) -> List:
        """Get KYB monitoring test functions."""
        test_functions = []
        
        try:
            from tests.test_kyb_monitoring_vies_integration import test_vies_validation
            from tests.test_kyb_monitoring_gleif_integration import test_gleif_lookup
            from tests.test_kyb_monitoring_sanctions_screening import test_sanctions_screening
            
            test_functions.extend([
                test_vies_validation,
                test_gleif_lookup,
                test_sanctions_screening
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import KYB monitoring tests: {str(e)}")
        
        return test_functions
    
    def _get_ai_agent_tests(self) -> List:
        """Get AI agent test functions."""
        test_functions = []
        
        try:
            from tests.test_ai_agent_comprehensive_router import test_router_agent
            from tests.test_ai_agent_comprehensive_specialized import test_specialized_agents
            from tests.test_ai_agent_comprehensive_supervisor import test_supervisor_agent
            
            test_functions.extend([
                test_router_agent,
                test_specialized_agents,
                test_supervisor_agent
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import AI agent tests: {str(e)}")
        
        return test_functions
    
    def _get_billing_tests(self) -> List:
        """Get billing test functions."""
        test_functions = []
        
        try:
            from tests.test_comprehensive_stripe_integration import (
                test_stripe_checkout,
                test_webhook_processing,
                test_subscription_management
            )
            
            from tests.test_usage_tracking_comprehensive import (
                test_usage_tracking,
                test_overage_calculation
            )
            
            test_functions.extend([
                test_stripe_checkout,
                test_webhook_processing,
                test_subscription_management,
                test_usage_tracking,
                test_overage_calculation
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import billing tests: {str(e)}")
        
        return test_functions
    
    def _get_calendar_tests(self) -> List:
        """Get calendar test functions."""
        test_functions = []
        
        try:
            from tests.test_calendar_oauth_comprehensive import test_google_oauth
            from tests.test_calendar_event_synchronization import test_event_sync
            
            test_functions.extend([
                test_google_oauth,
                test_event_sync
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import calendar tests: {str(e)}")
        
        return test_functions
    
    def _get_knowledge_tests(self) -> List:
        """Get knowledge management test functions."""
        test_functions = []
        
        try:
            from tests.test_knowledge_comprehensive import (
                test_document_processing,
                test_knowledge_search,
                test_rag_functionality
            )
            
            test_functions.extend([
                test_document_processing,
                test_knowledge_search,
                test_rag_functionality
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import knowledge tests: {str(e)}")
        
        return test_functions
    
    def _get_communication_tests(self) -> List:
        """Get communication channel test functions."""
        test_functions = []
        
        try:
            from tests.test_comprehensive_telegram_integration import test_telegram_integration
            from tests.test_comprehensive_signal_integration import test_signal_integration
            
            test_functions.extend([
                test_telegram_integration,
                test_signal_integration
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import communication tests: {str(e)}")
        
        return test_functions
    
    def _get_integration_tests(self) -> List:
        """Get integration test functions."""
        test_functions = []
        
        try:
            from tests.test_end_to_end_integration import (
                test_complete_user_journey,
                test_cross_component_integration
            )
            
            test_functions.extend([
                test_complete_user_journey,
                test_cross_component_integration
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import integration tests: {str(e)}")
        
        return test_functions
    
    def _get_performance_tests(self) -> List:
        """Get performance test functions."""
        test_functions = []
        
        try:
            from tests.test_performance_load import (
                test_concurrent_users,
                test_bulk_operations
            )
            
            test_functions.extend([
                test_concurrent_users,
                test_bulk_operations
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import performance tests: {str(e)}")
        
        return test_functions
    
    def _get_security_tests(self) -> List:
        """Get security test functions."""
        test_functions = []
        
        try:
            from tests.test_security_authentication import test_auth_security
            from tests.test_security_authorization import test_authz_security
            
            test_functions.extend([
                test_auth_security,
                test_authz_security
            ])
            
        except ImportError as e:
            self.logger.warning(f"Could not import security tests: {str(e)}")
        
        return test_functions
    
    # Helper methods for system monitoring
    async def _get_memory_usage(self) -> float:
        """Get current memory usage percentage."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except ImportError:
            return 0.0
    
    async def _get_cpu_usage(self) -> float:
        """Get current CPU usage percentage."""
        try:
            import psutil
            return psutil.cpu_percent(interval=None)
        except ImportError:
            return 0.0
    
    async def _collect_current_metrics(self) -> Dict[str, Any]:
        """Collect current system metrics."""
        return {
            'memory_usage': await self._get_memory_usage(),
            'cpu_usage': await self._get_cpu_usage(),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    async def _get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        return {
            'python_version': sys.version,
            'platform': sys.platform,
            'working_directory': os.getcwd(),
            'environment_variables': {k: v for k, v in os.environ.items() 
                                    if not any(s in k.lower() for s in ['password', 'secret', 'key', 'token'])}
        }
    
    async def _get_environment_info(self) -> Dict[str, Any]:
        """Get test environment information."""
        return {
            'test_directories': [str(p) for p in Path('tests').rglob('*') if p.is_dir()],
            'test_files_count': len(list(Path('tests').rglob('test_*.py'))),
            'config_files': [str(p) for p in Path('.').glob('*.py') if 'config' in p.name.lower()]
        }


async def main():
    """Main execution function."""
    print("Starting Final Test Execution System")
    print("=" * 80)
    
    # Configuration
    config = {
        'orchestrator': {
            'environment': {
                'database_url': 'sqlite:///test.db',
                'redis_url': 'redis://localhost:6379/1',
                'cleanup_on_exit': True
            }
        },
        'result_collector': {
            'monitoring_interval': 2.0,
            'response_time_warning': 2.0,
            'response_time_critical': 5.0,
            'error_rate_warning': 0.05,
            'error_rate_critical': 0.10
        }
    }
    
    # Create and run executor
    executor = FinalTestExecutor(config)
    
    try:
        # Execute complete test suite
        report = await executor.execute_complete_test_suite()
        
        print("\n" + "=" * 80)
        print("FINAL TEST EXECUTION COMPLETED")
        print("=" * 80)
        print(f"Overall Status: {report.overall_status}")
        print(f"Total Execution Time: {report.total_execution_time:.2f} seconds")
        print(f"Critical Issues: {len(report.critical_issues)}")
        print(f"User Actions Required: {len(report.user_action_required)}")
        print("=" * 80)
        
        return report
        
    except Exception as e:
        print(f"CRITICAL ERROR: {str(e)}")
        print(traceback.format_exc())
        return None


if __name__ == "__main__":
    # Run the final test execution
    asyncio.run(main())