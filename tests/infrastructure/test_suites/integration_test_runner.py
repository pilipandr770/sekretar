"""
Integration Test Runner

Registers and runs end-to-end and cross-component integration tests.
"""
from typing import List, Dict, Any
import logging

from tests.infrastructure.test_orchestrator import TestOrchestrator, TestCategory
from tests.infrastructure.test_suites.end_to_end_integration_tests import get_end_to_end_integration_tests
from tests.infrastructure.test_suites.cross_component_integration_tests import get_cross_component_integration_tests


class IntegrationTestRunner:
    """
    Runner for integration tests.
    
    Registers end-to-end and cross-component integration tests
    with the test orchestrator.
    """
    
    def __init__(self, orchestrator: TestOrchestrator):
        """Initialize integration test runner."""
        self.orchestrator = orchestrator
        self.logger = logging.getLogger(__name__)
    
    def register_integration_tests(self):
        """Register all integration tests with the orchestrator."""
        self.logger.info("Registering integration tests")
        
        # Register end-to-end integration tests
        end_to_end_tests = get_end_to_end_integration_tests()
        self.orchestrator.register_test_suite(TestCategory.INTEGRATION, end_to_end_tests)
        self.logger.info(f"Registered {len(end_to_end_tests)} end-to-end integration tests")
        
        # Register cross-component integration tests
        cross_component_tests = get_cross_component_integration_tests()
        self.orchestrator.register_test_suite(TestCategory.INTEGRATION, cross_component_tests)
        self.logger.info(f"Registered {len(cross_component_tests)} cross-component integration tests")
        
        total_tests = len(end_to_end_tests) + len(cross_component_tests)
        self.logger.info(f"Total integration tests registered: {total_tests}")
    
    async def run_integration_tests_only(self) -> Dict[str, Any]:
        """Run only integration tests."""
        self.logger.info("Running integration tests only")
        
        # Register integration tests
        self.register_integration_tests()
        
        # Run only integration category
        if TestCategory.INTEGRATION in self.orchestrator.test_suites:
            integration_suite_result = await self.orchestrator._execute_test_suite(
                TestCategory.INTEGRATION, 
                self.orchestrator.execution_context.real_company_data if self.orchestrator.execution_context else {}
            )
            
            return {
                'success': True,
                'suite_result': integration_suite_result,
                'total_tests': integration_suite_result.total_tests,
                'passed': integration_suite_result.passed,
                'failed': integration_suite_result.failed,
                'errors': integration_suite_result.errors
            }
        else:
            return {
                'success': False,
                'error': 'No integration tests registered'
            }


def setup_integration_testing(config: Dict[str, Any] = None) -> IntegrationTestRunner:
    """
    Setup integration testing with orchestrator.
    
    Args:
        config: Configuration for test orchestrator
        
    Returns:
        IntegrationTestRunner: Configured test runner
    """
    # Create test orchestrator
    orchestrator = TestOrchestrator(config)
    
    # Create integration test runner
    runner = IntegrationTestRunner(orchestrator)
    
    # Register integration tests
    runner.register_integration_tests()
    
    return runner


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def main():
        """Example of running integration tests."""
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        
        # Setup integration testing
        runner = setup_integration_testing()
        
        # Setup test environment (simplified for example)
        await runner.orchestrator._setup_test_environment()
        
        # Prepare test data
        real_company_data = await runner.orchestrator._prepare_real_company_data()
        
        # Run integration tests
        result = await runner.run_integration_tests_only()
        
        print(f"Integration tests completed:")
        print(f"Total tests: {result.get('total_tests', 0)}")
        print(f"Passed: {result.get('passed', 0)}")
        print(f"Failed: {result.get('failed', 0)}")
        print(f"Errors: {result.get('errors', 0)}")
        
        # Cleanup
        await runner.orchestrator._cleanup_test_environment()
    
    # Run the example
    asyncio.run(main())