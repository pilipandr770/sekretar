"""
Final Test Execution and Comprehensive Reporting System

This script implements task 16 from the comprehensive system testing specification:
- 16.1: Execute complete test suite with comprehensive metrics collection
- 16.2: Generate comprehensive final report with executive summary and user actions

Usage:
    python tests/infrastructure/run_final_test_execution_and_reporting.py
"""
import asyncio
import logging
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from tests.infrastructure.final_test_executor import FinalTestExecutor
from tests.infrastructure.final_report_generator import FinalReportGenerator, ReportFormat
from tests.infrastructure.models import ComprehensiveReport


class FinalTestExecutionAndReporting:
    """
    Main class that orchestrates the complete final test execution and reporting process.
    
    This implements both sub-tasks of task 16:
    - Execute complete test suite with comprehensive monitoring
    - Generate detailed final reports with executive summary and user actions
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """Initialize the final test execution and reporting system."""
        self.config = config or {}
        self.logger = self._setup_logging()
        
        # Initialize components
        self.test_executor = FinalTestExecutor(self.config.get('executor', {}))
        self.report_generator = FinalReportGenerator(self.config.get('report_generator', {}))
        
        # Execution tracking
        self.execution_start_time: Optional[datetime] = None
        self.execution_metadata: Dict[str, Any] = {}
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging for the execution and reporting system."""
        logger = logging.getLogger('final_test_execution_and_reporting')
        logger.setLevel(logging.INFO)
        
        # Create console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        return logger
    
    async def run_complete_final_test_execution_and_reporting(self) -> Dict[str, Any]:
        """
        Run the complete final test execution and reporting process.
        
        This method implements both task 16.1 and 16.2:
        1. Execute complete test suite with comprehensive metrics
        2. Generate comprehensive final report
        
        Returns:
            Dict containing execution results and generated report paths
        """
        self.execution_start_time = datetime.utcnow()
        
        self.logger.info("=" * 100)
        self.logger.info("STARTING FINAL TEST EXECUTION AND COMPREHENSIVE REPORTING")
        self.logger.info("=" * 100)
        self.logger.info(f"Execution started at: {self.execution_start_time}")
        
        try:
            # Task 16.1: Execute complete test suite
            self.logger.info("\n" + "=" * 80)
            self.logger.info("TASK 16.1: EXECUTING COMPLETE TEST SUITE")
            self.logger.info("=" * 80)
            
            comprehensive_report = await self._execute_complete_test_suite()
            
            # Task 16.2: Generate comprehensive final report
            self.logger.info("\n" + "=" * 80)
            self.logger.info("TASK 16.2: GENERATING COMPREHENSIVE FINAL REPORT")
            self.logger.info("=" * 80)
            
            generated_reports = await self._generate_comprehensive_final_report(comprehensive_report)
            
            # Create final execution summary
            execution_summary = await self._create_execution_summary(comprehensive_report, generated_reports)
            
            self.logger.info("\n" + "=" * 100)
            self.logger.info("FINAL TEST EXECUTION AND REPORTING COMPLETED SUCCESSFULLY")
            self.logger.info("=" * 100)
            
            return execution_summary
            
        except Exception as e:
            self.logger.error(f"CRITICAL ERROR in final test execution and reporting: {str(e)}")
            self.logger.error(traceback.format_exc())
            
            # Create emergency summary
            return await self._create_emergency_summary(str(e))
    
    async def _execute_complete_test_suite(self) -> ComprehensiveReport:
        """
        Execute complete test suite with comprehensive metrics collection.
        
        This implements task 16.1:
        - Run all test categories in proper sequence
        - Collect comprehensive performance and error metrics
        - Generate detailed execution logs and traces
        """
        self.logger.info("Executing complete test suite with comprehensive monitoring...")
        
        try:
            # Execute the comprehensive test suite
            comprehensive_report = await self.test_executor.execute_complete_test_suite()
            
            # Log execution results
            self._log_test_execution_results(comprehensive_report)
            
            # Store execution metadata
            self.execution_metadata.update({
                'test_execution_completed': True,
                'test_execution_time': comprehensive_report.total_execution_time,
                'total_test_suites': len(comprehensive_report.suite_results),
                'total_tests': sum(suite.total_tests for suite in comprehensive_report.suite_results),
                'overall_status': comprehensive_report.overall_status
            })
            
            self.logger.info("✅ Task 16.1 completed successfully: Complete test suite executed")
            return comprehensive_report
            
        except Exception as e:
            self.logger.error(f"❌ Task 16.1 failed: {str(e)}")
            raise
    
    async def _generate_comprehensive_final_report(self, comprehensive_report: ComprehensiveReport) -> Dict[str, str]:
        """
        Generate comprehensive final report with executive summary and user actions.
        
        This implements task 16.2:
        - Create executive summary with overall system health
        - Generate detailed issue reports with reproduction steps
        - Produce prioritized improvement plan with timelines
        - Document all required user actions with clear instructions
        """
        self.logger.info("Generating comprehensive final report...")
        
        try:
            # Prepare execution metadata for report
            execution_metadata = {
                'execution_start_time': self.execution_start_time.isoformat() if self.execution_start_time else None,
                'execution_end_time': datetime.utcnow().isoformat(),
                'total_execution_duration': (datetime.utcnow() - self.execution_start_time).total_seconds() if self.execution_start_time else 0,
                **self.execution_metadata
            }
            
            # Generate comprehensive final report
            generated_reports = await self.report_generator.generate_comprehensive_final_report(
                comprehensive_report,
                execution_metadata
            )
            
            # Log report generation results
            self._log_report_generation_results(generated_reports)
            
            self.logger.info("✅ Task 16.2 completed successfully: Comprehensive final report generated")
            return generated_reports
            
        except Exception as e:
            self.logger.error(f"❌ Task 16.2 failed: {str(e)}")
            raise
    
    def _log_test_execution_results(self, comprehensive_report: ComprehensiveReport):
        """Log test execution results summary."""
        self.logger.info("TEST EXECUTION RESULTS:")
        self.logger.info(f"  Overall Status: {comprehensive_report.overall_status}")
        self.logger.info(f"  Total Execution Time: {comprehensive_report.total_execution_time:.2f} seconds")
        self.logger.info(f"  Test Suites Executed: {len(comprehensive_report.suite_results)}")
        
        # Calculate totals
        total_tests = sum(suite.total_tests for suite in comprehensive_report.suite_results)
        total_passed = sum(suite.passed for suite in comprehensive_report.suite_results)
        total_failed = sum(suite.failed for suite in comprehensive_report.suite_results)
        total_errors = sum(suite.errors for suite in comprehensive_report.suite_results)
        
        self.logger.info(f"  Total Tests: {total_tests}")
        self.logger.info(f"  Passed: {total_passed} ({(total_passed/total_tests)*100:.1f}%)")
        self.logger.info(f"  Failed: {total_failed} ({(total_failed/total_tests)*100:.1f}%)")
        self.logger.info(f"  Errors: {total_errors} ({(total_errors/total_tests)*100:.1f}%)")
        
        # Log critical findings
        critical_issues = len(comprehensive_report.critical_issues)
        improvement_actions = len(comprehensive_report.improvement_plan)
        user_actions = len(comprehensive_report.user_action_required)
        
        self.logger.info(f"  Critical Issues Detected: {critical_issues}")
        self.logger.info(f"  Improvement Actions Generated: {improvement_actions}")
        self.logger.info(f"  User Actions Required: {user_actions}")
        
        # Log suite-by-suite results
        self.logger.info("\nTEST SUITE BREAKDOWN:")
        for suite in comprehensive_report.suite_results:
            success_rate = (suite.passed / suite.total_tests * 100) if suite.total_tests > 0 else 0
            self.logger.info(f"  {suite.suite_name}: {suite.passed}/{suite.total_tests} passed ({success_rate:.1f}%) - {suite.execution_time:.2f}s")
    
    def _log_report_generation_results(self, generated_reports: Dict[str, str]):
        """Log report generation results."""
        self.logger.info("REPORT GENERATION RESULTS:")
        self.logger.info(f"  Reports Generated: {len(generated_reports)}")
        
        for format_name, file_path in generated_reports.items():
            file_size = Path(file_path).stat().st_size if Path(file_path).exists() else 0
            self.logger.info(f"  {format_name.upper()}: {file_path} ({file_size:,} bytes)")
        
        self.logger.info("\nREPORT CONTENTS:")
        self.logger.info("  ✓ Executive summary with overall system health")
        self.logger.info("  ✓ Detailed issue reports with reproduction steps")
        self.logger.info("  ✓ Prioritized improvement plan with timelines")
        self.logger.info("  ✓ User action guides with clear instructions")
        self.logger.info("  ✓ Test execution summary and metrics")
        self.logger.info("  ✓ Performance analysis and recommendations")
    
    async def _create_execution_summary(self, comprehensive_report: ComprehensiveReport, 
                                      generated_reports: Dict[str, str]) -> Dict[str, Any]:
        """Create final execution summary."""
        execution_end_time = datetime.utcnow()
        total_duration = (execution_end_time - self.execution_start_time).total_seconds() if self.execution_start_time else 0
        
        # Calculate test statistics
        total_tests = sum(suite.total_tests for suite in comprehensive_report.suite_results)
        total_passed = sum(suite.passed for suite in comprehensive_report.suite_results)
        success_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0
        
        return {
            'execution_summary': {
                'start_time': self.execution_start_time.isoformat() if self.execution_start_time else None,
                'end_time': execution_end_time.isoformat(),
                'total_duration_seconds': total_duration,
                'total_duration_formatted': f"{total_duration/60:.1f} minutes",
                'status': 'COMPLETED_SUCCESSFULLY'
            },
            'task_16_1_results': {
                'status': 'COMPLETED',
                'description': 'Execute complete test suite',
                'test_suites_executed': len(comprehensive_report.suite_results),
                'total_tests_run': total_tests,
                'overall_success_rate': success_rate,
                'test_execution_time': comprehensive_report.total_execution_time,
                'critical_issues_detected': len(comprehensive_report.critical_issues),
                'performance_metrics_collected': True,
                'execution_logs_generated': True
            },
            'task_16_2_results': {
                'status': 'COMPLETED',
                'description': 'Generate comprehensive final report',
                'reports_generated': list(generated_reports.keys()),
                'report_files': generated_reports,
                'executive_summary_created': True,
                'detailed_issue_reports_created': len(comprehensive_report.critical_issues),
                'improvement_plan_created': len(comprehensive_report.improvement_plan),
                'user_action_guides_created': len(comprehensive_report.user_action_required)
            },
            'overall_results': {
                'system_health_status': comprehensive_report.overall_status,
                'critical_issues_count': len([i for i in comprehensive_report.critical_issues 
                                            if i.severity.value == 'critical']),
                'high_priority_issues_count': len([i for i in comprehensive_report.critical_issues 
                                                 if i.severity.value == 'high']),
                'immediate_user_actions_required': len([a for a in comprehensive_report.user_action_required 
                                                      if a.urgency.value == 'immediate']),
                'next_steps': [
                    "Review generated comprehensive reports",
                    "Address critical issues identified in the reports",
                    "Execute user actions marked as immediate priority",
                    "Implement improvement plan items based on priority",
                    "Schedule follow-up testing after fixes are applied"
                ]
            }
        }
    
    async def _create_emergency_summary(self, error_message: str) -> Dict[str, Any]:
        """Create emergency summary when execution fails."""
        execution_end_time = datetime.utcnow()
        total_duration = (execution_end_time - self.execution_start_time).total_seconds() if self.execution_start_time else 0
        
        return {
            'execution_summary': {
                'start_time': self.execution_start_time.isoformat() if self.execution_start_time else None,
                'end_time': execution_end_time.isoformat(),
                'total_duration_seconds': total_duration,
                'status': 'FAILED'
            },
            'error_details': {
                'error_message': error_message,
                'failure_point': 'During test execution or report generation',
                'immediate_actions_required': [
                    "Review execution logs for detailed error information",
                    "Check system requirements and dependencies",
                    "Verify test environment configuration",
                    "Contact technical support if issues persist"
                ]
            },
            'task_16_1_results': {
                'status': 'FAILED' if 'test_execution_completed' not in self.execution_metadata else 'COMPLETED',
                'description': 'Execute complete test suite'
            },
            'task_16_2_results': {
                'status': 'FAILED',
                'description': 'Generate comprehensive final report'
            }
        }


async def main():
    """Main execution function."""
    print("Final Test Execution and Comprehensive Reporting System")
    print("=" * 80)
    print("Implementing Task 16: Create final test execution and reporting")
    print("  - Task 16.1: Execute complete test suite")
    print("  - Task 16.2: Generate comprehensive final report")
    print("=" * 80)
    
    # Configuration
    config = {
        'executor': {
            'orchestrator': {
                'environment': {
                    'database_url': 'sqlite:///test_comprehensive.db',
                    'redis_url': 'redis://localhost:6379/2',
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
        },
        'report_generator': {
            'output_formats': [ReportFormat.HTML, ReportFormat.JSON, ReportFormat.MARKDOWN],
            'include_charts': True,
            'include_detailed_logs': True
        }
    }
    
    # Create and run the final test execution and reporting system
    system = FinalTestExecutionAndReporting(config)
    
    try:
        # Run complete process
        results = await system.run_complete_final_test_execution_and_reporting()
        
        # Display final results
        print("\n" + "=" * 80)
        print("FINAL EXECUTION RESULTS")
        print("=" * 80)
        
        execution_summary = results.get('execution_summary', {})
        print(f"Status: {execution_summary.get('status', 'Unknown')}")
        print(f"Duration: {execution_summary.get('total_duration_formatted', 'Unknown')}")
        
        task_16_1 = results.get('task_16_1_results', {})
        print(f"\nTask 16.1 Status: {task_16_1.get('status', 'Unknown')}")
        if task_16_1.get('status') == 'COMPLETED':
            print(f"  Test Suites Executed: {task_16_1.get('test_suites_executed', 0)}")
            print(f"  Total Tests Run: {task_16_1.get('total_tests_run', 0)}")
            print(f"  Success Rate: {task_16_1.get('overall_success_rate', 0):.1f}%")
            print(f"  Critical Issues: {task_16_1.get('critical_issues_detected', 0)}")
        
        task_16_2 = results.get('task_16_2_results', {})
        print(f"\nTask 16.2 Status: {task_16_2.get('status', 'Unknown')}")
        if task_16_2.get('status') == 'COMPLETED':
            print(f"  Reports Generated: {', '.join(task_16_2.get('reports_generated', []))}")
            print(f"  Report Files:")
            for format_name, file_path in task_16_2.get('report_files', {}).items():
                print(f"    {format_name.upper()}: {file_path}")
        
        overall = results.get('overall_results', {})
        if overall:
            print(f"\nOverall System Health: {overall.get('system_health_status', 'Unknown')}")
            print(f"Critical Issues: {overall.get('critical_issues_count', 0)}")
            print(f"High Priority Issues: {overall.get('high_priority_issues_count', 0)}")
            print(f"Immediate Actions Required: {overall.get('immediate_user_actions_required', 0)}")
            
            print("\nNext Steps:")
            for i, step in enumerate(overall.get('next_steps', []), 1):
                print(f"  {i}. {step}")
        
        print("=" * 80)
        return results
        
    except Exception as e:
        print(f"\nCRITICAL ERROR: {str(e)}")
        print(traceback.format_exc())
        return None


if __name__ == "__main__":
    # Run the final test execution and reporting system
    asyncio.run(main())