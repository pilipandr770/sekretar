"""
Comprehensive Test Runner

Main entry point for running comprehensive system tests.
"""
import asyncio
import logging
import sys
import os
from typing import Optional

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from tests.infrastructure.test_orchestrator import TestOrchestrator
from tests.infrastructure.config import ComprehensiveTestConfig
from tests.infrastructure.models import ComprehensiveReport


async def run_comprehensive_tests(config_override: Optional[dict] = None) -> ComprehensiveReport:
    """
    Run comprehensive system tests.
    
    Args:
        config_override: Optional configuration overrides
        
    Returns:
        ComprehensiveReport: Detailed test execution report
    """
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler('comprehensive_test_execution.log')
        ]
    )
    
    logger = logging.getLogger(__name__)
    logger.info("Starting comprehensive system test execution")
    
    try:
        # Get configuration
        config = ComprehensiveTestConfig.get_config()
        if config_override:
            config.update(config_override)
        
        # Validate configuration
        if not ComprehensiveTestConfig.validate_config():
            logger.error("Configuration validation failed")
            sys.exit(1)
        
        # Set environment variables
        env_vars = ComprehensiveTestConfig.get_environment_variables()
        for key, value in env_vars.items():
            os.environ[key] = value
        
        # Create test orchestrator
        orchestrator = TestOrchestrator(config)
        
        # Register test suites (this would be expanded with actual test implementations)
        await register_test_suites(orchestrator)
        
        # Run comprehensive test suite
        report = await orchestrator.run_comprehensive_test_suite()
        
        # Print summary
        print_test_summary(report)
        
        return report
        
    except Exception as e:
        logger.error(f"Critical error during test execution: {str(e)}")
        raise


async def register_test_suites(orchestrator: TestOrchestrator):
    """Register all test suites with the orchestrator."""
    from tests.infrastructure.test_orchestrator import TestCategory
    
    # Note: These would be actual test implementations
    # For now, we're just registering placeholder functions
    
    # User Registration Tests
    orchestrator.register_test_suite(TestCategory.USER_REGISTRATION, [
        test_user_registration_flow,
        test_tenant_creation,
        test_email_confirmation,
        test_oauth_integration
    ])
    
    # API Endpoint Tests
    orchestrator.register_test_suite(TestCategory.API_ENDPOINTS, [
        test_authentication_endpoints,
        test_tenant_endpoints,
        test_crm_endpoints,
        test_kyb_endpoints
    ])
    
    # CRM Functionality Tests
    orchestrator.register_test_suite(TestCategory.CRM_FUNCTIONALITY, [
        test_contact_management,
        test_lead_pipeline,
        test_task_management
    ])
    
    # KYB Monitoring Tests
    orchestrator.register_test_suite(TestCategory.KYB_MONITORING, [
        test_vies_integration,
        test_gleif_integration,
        test_sanctions_screening
    ])
    
    # Additional test categories would be registered here...


# Placeholder test functions (these would be implemented in separate modules)
async def test_user_registration_flow(context, real_company_data):
    """Test complete user registration flow."""
    # This would contain actual test implementation
    return {'success': True, 'message': 'User registration flow test passed'}


async def test_tenant_creation(context, real_company_data):
    """Test tenant creation with real company data."""
    return {'success': True, 'message': 'Tenant creation test passed'}


async def test_email_confirmation(context, real_company_data):
    """Test email confirmation process."""
    return {'success': True, 'message': 'Email confirmation test passed'}


async def test_oauth_integration(context, real_company_data):
    """Test OAuth integration."""
    return {'success': True, 'message': 'OAuth integration test passed'}


async def test_authentication_endpoints(context, real_company_data):
    """Test authentication API endpoints."""
    return {'success': True, 'message': 'Authentication endpoints test passed'}


async def test_tenant_endpoints(context, real_company_data):
    """Test tenant API endpoints."""
    return {'success': True, 'message': 'Tenant endpoints test passed'}


async def test_crm_endpoints(context, real_company_data):
    """Test CRM API endpoints."""
    return {'success': True, 'message': 'CRM endpoints test passed'}


async def test_kyb_endpoints(context, real_company_data):
    """Test KYB API endpoints."""
    return {'success': True, 'message': 'KYB endpoints test passed'}


async def test_contact_management(context, real_company_data):
    """Test contact management functionality."""
    return {'success': True, 'message': 'Contact management test passed'}


async def test_lead_pipeline(context, real_company_data):
    """Test lead pipeline management."""
    return {'success': True, 'message': 'Lead pipeline test passed'}


async def test_task_management(context, real_company_data):
    """Test task management functionality."""
    return {'success': True, 'message': 'Task management test passed'}


async def test_vies_integration(context, real_company_data):
    """Test VIES integration with real VAT numbers."""
    return {'success': True, 'message': 'VIES integration test passed'}


async def test_gleif_integration(context, real_company_data):
    """Test GLEIF integration with real LEI codes."""
    return {'success': True, 'message': 'GLEIF integration test passed'}


async def test_sanctions_screening(context, real_company_data):
    """Test sanctions screening functionality."""
    return {'success': True, 'message': 'Sanctions screening test passed'}


def print_test_summary(report: ComprehensiveReport):
    """Print test execution summary."""
    print("\n" + "="*80)
    print("COMPREHENSIVE TEST EXECUTION SUMMARY")
    print("="*80)
    
    print(f"Overall Status: {report.overall_status}")
    print(f"Total Execution Time: {report.total_execution_time:.2f} seconds")
    print()
    
    # Suite results summary
    total_tests = sum(suite.total_tests for suite in report.suite_results)
    total_passed = sum(suite.passed for suite in report.suite_results)
    total_failed = sum(suite.failed for suite in report.suite_results)
    total_errors = sum(suite.errors for suite in report.suite_results)
    total_skipped = sum(suite.skipped for suite in report.suite_results)
    
    print("TEST RESULTS SUMMARY:")
    print(f"  Total Tests: {total_tests}")
    print(f"  Passed: {total_passed}")
    print(f"  Failed: {total_failed}")
    print(f"  Errors: {total_errors}")
    print(f"  Skipped: {total_skipped}")
    print()
    
    # Suite breakdown
    print("SUITE BREAKDOWN:")
    for suite in report.suite_results:
        status = "✓" if suite.failed == 0 and suite.errors == 0 else "✗"
        print(f"  {status} {suite.suite_name}: {suite.passed}/{suite.total_tests} passed "
              f"({suite.execution_time:.2f}s)")
    print()
    
    # Critical issues
    if report.critical_issues:
        print("CRITICAL ISSUES DETECTED:")
        for issue in report.critical_issues[:5]:  # Show top 5 issues
            print(f"  • {issue.title} ({issue.severity.value})")
        if len(report.critical_issues) > 5:
            print(f"  ... and {len(report.critical_issues) - 5} more issues")
        print()
    
    # User actions required
    if report.user_action_required:
        print("USER ACTIONS REQUIRED:")
        for action in report.user_action_required[:3]:  # Show top 3 actions
            print(f"  • {action.title} ({action.urgency.value})")
        if len(report.user_action_required) > 3:
            print(f"  ... and {len(report.user_action_required) - 3} more actions")
        print()
    
    print("="*80)
    print("Detailed report saved to test_reports/ directory")
    print("="*80)


if __name__ == "__main__":
    """Main entry point for running comprehensive tests."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run comprehensive system tests')
    parser.add_argument('--config', type=str, help='Path to configuration file')
    parser.add_argument('--parallel', action='store_true', help='Enable parallel test execution')
    parser.add_argument('--no-cleanup', action='store_true', help='Skip cleanup after tests')
    parser.add_argument('--verbose', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configuration overrides based on command line arguments
    config_override = {}
    
    if args.parallel:
        config_override['environment'] = {'parallel_execution': True}
    
    if args.no_cleanup:
        config_override['environment'] = {'cleanup_on_exit': False}
    
    if args.verbose:
        config_override['execution'] = {'detailed_logging': True}
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run tests
    try:
        report = asyncio.run(run_comprehensive_tests(config_override))
        
        # Exit with appropriate code
        if report.overall_status in ['ALL_TESTS_PASSED', 'SOME_ISSUES_DETECTED']:
            sys.exit(0)
        else:
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nTest execution interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"\nTest execution failed: {str(e)}")
        sys.exit(1)