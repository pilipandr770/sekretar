"""
Demonstration script for comprehensive testing infrastructure.

This script shows how to use the testing infrastructure components.
"""
import asyncio
import logging
import sys
import os

# Add the project root to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from tests.infrastructure.test_orchestrator import TestOrchestrator, TestCategory
from tests.infrastructure.test_environment import TestEnvironment
from tests.infrastructure.test_data_manager import TestDataManager
from tests.infrastructure.config import ComprehensiveTestConfig


async def demo_test_environment():
    """Demonstrate test environment setup and cleanup."""
    print("=== Test Environment Demo ===")
    
    config = {
        'database_url': 'sqlite:///demo_test.db',
        'redis_url': 'redis://localhost:6379/15',
        'cleanup_on_exit': True
    }
    
    test_env = TestEnvironment(config)
    
    print("Setting up test environment...")
    success = await test_env.setup()
    
    if success:
        print(f"✓ Test environment setup successful")
        print(f"  - Temporary directory: {test_env.temp_dir}")
        print(f"  - Database URL: {test_env.database_url}")
        print(f"  - Redis URL: {test_env.redis_url}")
        
        # Get environment variables
        env_vars = test_env.get_environment_variables()
        print(f"  - Environment variables: {len(env_vars)} variables set")
        
        print("Cleaning up test environment...")
        await test_env.cleanup()
        print("✓ Test environment cleanup completed")
    else:
        print("✗ Test environment setup failed")


async def demo_test_data_manager():
    """Demonstrate test data manager functionality."""
    print("\n=== Test Data Manager Demo ===")
    
    config = {
        'vies_api_url': 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService',
        'gleif_api_url': 'https://api.gleif.org/api/v1',
        'rate_limits': {'vies': 10, 'gleif': 60},
        'timeout_seconds': 10,  # Shorter timeout for demo
        'retry_attempts': 1
    }
    
    data_manager = TestDataManager(config)
    
    print("Initializing test data manager...")
    await data_manager.initialize()
    print("✓ Test data manager initialized")
    
    # Get predefined companies
    print("Loading predefined company data...")
    predefined_companies = await data_manager._get_predefined_companies()
    print(f"✓ Loaded {len(predefined_companies)} predefined companies:")
    
    for company_id, company_info in list(predefined_companies.items())[:3]:  # Show first 3
        print(f"  - {company_id}: {company_info['name']} ({company_info['country']})")
    
    # Test company data validation
    from tests.infrastructure.models import CompanyData
    
    test_company = CompanyData(
        name="Demo Company Ltd",
        vat_number="GB123456789",
        lei_code="DEMO123456789012345",
        country_code="GB",
        address="123 Demo Street, Demo City",
        industry="Technology",
        size="SME",
        source="demo",
        validation_status="PENDING"
    )
    
    is_valid = data_manager._is_company_data_valid(test_company)
    print(f"✓ Company data validation: {'Valid' if is_valid else 'Invalid'}")
    
    print("Cleaning up test data manager...")
    await data_manager.cleanup()
    print("✓ Test data manager cleanup completed")


async def demo_test_orchestrator():
    """Demonstrate test orchestrator functionality."""
    print("\n=== Test Orchestrator Demo ===")
    
    config = ComprehensiveTestConfig.get_config()
    
    # Override config for demo
    config['environment']['cleanup_on_exit'] = True
    config['data_manager']['timeout_seconds'] = 5
    
    orchestrator = TestOrchestrator(config)
    print("✓ Test orchestrator created")
    
    # Define demo test functions
    async def demo_passing_test(context, real_company_data):
        """Demo test that passes."""
        print("  Running demo passing test...")
        await asyncio.sleep(0.1)  # Simulate test work
        return {'success': True, 'message': 'Demo test passed successfully'}
    
    async def demo_failing_test(context, real_company_data):
        """Demo test that fails."""
        print("  Running demo failing test...")
        await asyncio.sleep(0.1)  # Simulate test work
        return {'success': False, 'error': 'Demo test failed as expected'}
    
    def demo_sync_test(context, real_company_data):
        """Demo synchronous test."""
        print("  Running demo sync test...")
        return {'success': True, 'message': 'Sync test completed'}
    
    # Register test suites
    orchestrator.register_test_suite(TestCategory.USER_REGISTRATION, [
        demo_passing_test,
        demo_sync_test
    ])
    
    orchestrator.register_test_suite(TestCategory.API_ENDPOINTS, [
        demo_failing_test
    ])
    
    print(f"✓ Registered {len(orchestrator.test_suites)} test suites")
    
    # Execute single test to demonstrate
    print("Executing single test...")
    result = await orchestrator._execute_single_test(demo_passing_test, {})
    print(f"✓ Test result: {result.status.value} ({result.execution_time:.3f}s)")
    
    print("Demo orchestrator completed")


async def demo_configuration():
    """Demonstrate configuration management."""
    print("\n=== Configuration Demo ===")
    
    # Get full configuration
    config = ComprehensiveTestConfig.get_config()
    print(f"✓ Configuration loaded with {len(config)} sections:")
    
    for section_name, section_config in config.items():
        if isinstance(section_config, dict):
            print(f"  - {section_name}: {len(section_config)} settings")
        else:
            print(f"  - {section_name}: {type(section_config).__name__}")
    
    # Get environment variables
    env_vars = ComprehensiveTestConfig.get_environment_variables()
    print(f"✓ Environment variables: {len(env_vars)} variables")
    
    # Show some key environment variables
    key_vars = ['TESTING', 'FLASK_ENV', 'DATABASE_URL', 'REDIS_URL']
    for var in key_vars:
        if var in env_vars:
            print(f"  - {var}: {env_vars[var]}")
    
    # Validate configuration
    is_valid = ComprehensiveTestConfig.validate_config()
    print(f"✓ Configuration validation: {'Valid' if is_valid else 'Invalid'}")


async def main():
    """Main demo function."""
    print("Comprehensive Testing Infrastructure Demo")
    print("=" * 50)
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # Run demos
        await demo_configuration()
        await demo_test_environment()
        await demo_test_data_manager()
        await demo_test_orchestrator()
        
        print("\n" + "=" * 50)
        print("✓ All demos completed successfully!")
        print("\nThe comprehensive testing infrastructure is ready to use.")
        print("Run 'python tests/infrastructure/runner.py' to execute full tests.")
        
    except Exception as e:
        print(f"\n✗ Demo failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    """Run the demo."""
    exit_code = asyncio.run(main())
    sys.exit(exit_code)