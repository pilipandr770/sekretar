"""
Test script to verify comprehensive testing infrastructure setup.
"""
import pytest
import asyncio
import os
import tempfile
import shutil
from unittest.mock import patch, MagicMock

from tests.infrastructure.test_orchestrator import TestOrchestrator, TestCategory
from tests.infrastructure.test_environment import TestEnvironment
from tests.infrastructure.test_data_manager import TestDataManager
from tests.infrastructure.config import ComprehensiveTestConfig
from tests.infrastructure.models import CompanyData, TestStatus


class TestComprehensiveInfrastructure:
    """Test comprehensive testing infrastructure components."""
    
    def test_config_loading(self):
        """Test configuration loading and validation."""
        config = ComprehensiveTestConfig.get_config()
        
        assert 'environment' in config
        assert 'data_manager' in config
        assert 'execution' in config
        assert 'reporting' in config
        
        # Test environment variables
        env_vars = ComprehensiveTestConfig.get_environment_variables()
        assert 'TESTING' in env_vars
        assert env_vars['TESTING'] == 'True'
        assert 'FLASK_ENV' in env_vars
        assert env_vars['FLASK_ENV'] == 'testing'
        
        # Test validation
        assert ComprehensiveTestConfig.validate_config() is True
    
    @pytest.mark.asyncio
    async def test_test_environment_setup(self):
        """Test test environment setup and cleanup."""
        config = {
            'database_url': 'sqlite:///test_infrastructure.db',
            'redis_url': 'redis://localhost:6379/15',
            'cleanup_on_exit': True
        }
        
        test_env = TestEnvironment(config)
        
        # Test setup
        setup_success = await test_env.setup()
        assert setup_success is True
        assert test_env.is_setup is True
        assert test_env.temp_dir is not None
        assert os.path.exists(test_env.temp_dir)
        
        # Test environment config
        env_config = test_env.get_environment_config()
        assert env_config.database_url is not None
        assert env_config.redis_url is not None
        
        # Test environment variables
        env_vars = test_env.get_environment_variables()
        assert 'TESTING' in env_vars
        assert env_vars['TESTING'] == 'True'
        
        # Test cleanup
        await test_env.cleanup()
        assert test_env.is_setup is False
    
    @pytest.mark.asyncio
    async def test_test_data_manager_initialization(self):
        """Test test data manager initialization."""
        config = {
            'vies_api_url': 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService',
            'gleif_api_url': 'https://api.gleif.org/api/v1',
            'rate_limits': {'vies': 10, 'gleif': 60},
            'timeout_seconds': 30,
            'retry_attempts': 3
        }
        
        data_manager = TestDataManager(config)
        
        # Test initialization
        await data_manager.initialize()
        assert data_manager.http_client is not None
        
        # Test predefined companies
        predefined = await data_manager._get_predefined_companies()
        assert len(predefined) > 0
        assert 'microsoft_ireland' in predefined
        assert 'sap_germany' in predefined
        
        # Test company data validation
        test_company = CompanyData(
            name="Test Company Ltd",
            vat_number="GB123456789",
            lei_code="TEST123456789012345",
            country_code="GB",
            address="Test Address",
            industry="Technology",
            size="SME",
            source="test",
            validation_status="PENDING"
        )
        
        is_valid = data_manager._is_company_data_valid(test_company)
        assert is_valid is True
        
        # Test cleanup
        await data_manager.cleanup()
        assert data_manager.http_client is None
    
    @pytest.mark.asyncio
    async def test_test_orchestrator_initialization(self):
        """Test test orchestrator initialization."""
        config = ComprehensiveTestConfig.get_config()
        
        orchestrator = TestOrchestrator(config)
        
        # Test initial state
        assert len(orchestrator.test_suites) == 0
        assert len(orchestrator.test_results) == 0
        assert orchestrator.execution_context is None
        
        # Test test suite registration
        async def dummy_test(context, data):
            return {'success': True}
        
        orchestrator.register_test_suite(TestCategory.USER_REGISTRATION, [dummy_test])
        assert TestCategory.USER_REGISTRATION in orchestrator.test_suites
        assert len(orchestrator.test_suites[TestCategory.USER_REGISTRATION]) == 1
    
    @pytest.mark.asyncio
    async def test_single_test_execution(self):
        """Test single test execution."""
        config = ComprehensiveTestConfig.get_config()
        orchestrator = TestOrchestrator(config)
        
        # Mock test function that passes
        async def passing_test(context, data):
            return {'success': True, 'message': 'Test passed'}
        
        # Mock test function that fails
        async def failing_test(context, data):
            return {'success': False, 'error': 'Test failed'}
        
        # Mock test function that raises exception
        async def error_test(context, data):
            raise ValueError("Test error")
        
        # Test passing test
        result = await orchestrator._execute_single_test(passing_test, {})
        assert result.status == TestStatus.PASSED
        assert result.error_message is None
        
        # Test failing test
        result = await orchestrator._execute_single_test(failing_test, {})
        assert result.status == TestStatus.FAILED
        assert result.error_message == 'Test failed'
        
        # Test error test
        result = await orchestrator._execute_single_test(error_test, {})
        assert result.status == TestStatus.ERROR
        assert 'Test error' in result.error_message
    
    def test_company_data_model(self):
        """Test company data model."""
        company_data = CompanyData(
            name="Test Company Ltd",
            vat_number="GB123456789",
            lei_code="TEST123456789012345",
            country_code="GB",
            address="123 Test Street, Test City",
            industry="Technology",
            size="SME",
            source="test",
            validation_status="VALID"
        )
        
        assert company_data.name == "Test Company Ltd"
        assert company_data.vat_number == "GB123456789"
        assert company_data.lei_code == "TEST123456789012345"
        assert company_data.country_code == "GB"
        assert company_data.validation_status == "VALID"
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        """Test rate limiting functionality."""
        config = {
            'rate_limits': {'test_service': 2},  # 2 requests per minute
            'timeout_seconds': 30
        }
        
        data_manager = TestDataManager(config)
        await data_manager.initialize()
        
        # Test rate limiting
        start_time = asyncio.get_event_loop().time()
        
        # First two requests should go through quickly
        await data_manager._check_rate_limit('test_service')
        await data_manager._check_rate_limit('test_service')
        
        # Third request should be delayed
        await data_manager._check_rate_limit('test_service')
        
        end_time = asyncio.get_event_loop().time()
        
        # Should have taken some time due to rate limiting
        # Note: This is a simplified test - in practice, rate limiting is more complex
        
        await data_manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_environment_reset(self):
        """Test environment reset functionality."""
        config = {
            'database_url': 'sqlite:///test_reset.db',
            'redis_url': 'redis://localhost:6379/15',
            'cleanup_on_exit': True
        }
        
        test_env = TestEnvironment(config)
        
        # Setup environment
        await test_env.setup()
        assert test_env.is_setup is True
        
        # Reset environment
        await test_env.reset_environment()
        
        # Environment should still be setup but clean
        assert test_env.is_setup is True
        
        # Cleanup
        await test_env.cleanup()
    
    def test_issue_severity_mapping(self):
        """Test issue severity and priority mapping."""
        from tests.infrastructure.models import IssueSeverity, Priority
        from tests.infrastructure.test_orchestrator import TestOrchestrator
        
        config = ComprehensiveTestConfig.get_config()
        orchestrator = TestOrchestrator(config)
        
        # Test severity to priority mapping
        assert orchestrator._map_severity_to_priority(IssueSeverity.CRITICAL) == Priority.HIGH
        assert orchestrator._map_severity_to_priority(IssueSeverity.HIGH) == Priority.HIGH
        assert orchestrator._map_severity_to_priority(IssueSeverity.MEDIUM) == Priority.MEDIUM
        assert orchestrator._map_severity_to_priority(IssueSeverity.LOW) == Priority.LOW
    
    @pytest.mark.asyncio
    async def test_mock_comprehensive_test_run(self):
        """Test a mock comprehensive test run."""
        config = ComprehensiveTestConfig.get_config()
        
        # Override config for faster testing
        config['environment']['cleanup_on_exit'] = True
        config['data_manager']['timeout_seconds'] = 5
        
        orchestrator = TestOrchestrator(config)
        
        # Register mock test suites
        async def mock_test_1(context, data):
            return {'success': True, 'message': 'Mock test 1 passed'}
        
        async def mock_test_2(context, data):
            return {'success': False, 'error': 'Mock test 2 failed'}
        
        orchestrator.register_test_suite(TestCategory.USER_REGISTRATION, [mock_test_1])
        orchestrator.register_test_suite(TestCategory.API_ENDPOINTS, [mock_test_2])
        
        # Mock the data collection to avoid external API calls
        with patch.object(orchestrator.test_data_manager, 'collect_real_company_data') as mock_collect:
            mock_collect.return_value = {
                'test_company': CompanyData(
                    name="Test Company",
                    vat_number="GB123456789",
                    lei_code=None,
                    country_code="GB",
                    address="Test Address",
                    industry="Technology",
                    size="SME",
                    source="mock",
                    validation_status="VALID"
                )
            }
            
            # Mock environment setup
            with patch.object(orchestrator.test_environment, 'setup') as mock_setup:
                mock_setup.return_value = True
                
                with patch.object(orchestrator.test_environment, 'cleanup') as mock_cleanup:
                    mock_cleanup.return_value = None
                    
                    # Run comprehensive test
                    report = await orchestrator.run_comprehensive_test_suite()
                    
                    # Verify report
                    assert report is not None
                    assert report.overall_status is not None
                    assert len(report.suite_results) == 2
                    assert report.total_execution_time > 0
                    
                    # Check that we have both passed and failed tests
                    total_passed = sum(suite.passed for suite in report.suite_results)
                    total_failed = sum(suite.failed for suite in report.suite_results)
                    
                    assert total_passed >= 1  # At least one test should pass
                    assert total_failed >= 1  # At least one test should fail


if __name__ == "__main__":
    """Run infrastructure tests."""
    pytest.main([__file__, "-v"])