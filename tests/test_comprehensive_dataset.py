"""
Test script for comprehensive test dataset functionality.

This script tests the comprehensive test dataset builder and validation mechanisms.
"""
import asyncio
import pytest
import logging
from datetime import datetime, timedelta
from typing import Dict, Any

from tests.infrastructure.config import ComprehensiveTestConfig
from tests.infrastructure.test_dataset_builder import ComprehensiveTestDatasetBuilder
from tests.infrastructure.data_validation_refresh import DataValidationRefreshManager
from tests.infrastructure.models import CompanyData


# Configure logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TestComprehensiveDataset:
    """Test comprehensive dataset functionality."""
    
    @pytest.fixture
    async def dataset_builder(self):
        """Create dataset builder for testing."""
        config = ComprehensiveTestConfig.get_config()['data_manager']
        builder = ComprehensiveTestDatasetBuilder(config)
        await builder.initialize()
        yield builder
        await builder.cleanup()
    
    @pytest.fixture
    async def validation_manager(self):
        """Create validation manager for testing."""
        config = ComprehensiveTestConfig.get_config()['data_manager']
        manager = DataValidationRefreshManager(config)
        await manager.initialize()
        yield manager
        await manager.cleanup()
    
    @pytest.mark.asyncio
    async def test_build_comprehensive_dataset(self, dataset_builder):
        """Test building comprehensive dataset."""
        logger.info("Testing comprehensive dataset building")
        
        # Build dataset
        dataset = await dataset_builder.build_comprehensive_dataset()
        
        # Verify dataset was built
        assert isinstance(dataset, dict)
        assert len(dataset) > 0
        
        # Verify dataset contains companies from different countries
        countries = set()
        industries = set()
        
        for company in dataset.values():
            assert isinstance(company, CompanyData)
            assert company.name
            assert company.country_code
            assert len(company.country_code) == 2
            
            countries.add(company.country_code)
            if company.industry:
                industries.add(company.industry)
        
        # Should have companies from multiple countries
        assert len(countries) >= 3
        logger.info(f"Dataset contains companies from {len(countries)} countries: {sorted(countries)}")
        
        # Should have companies from multiple industries
        assert len(industries) >= 3
        logger.info(f"Dataset contains companies from {len(industries)} industries: {sorted(industries)}")
        
        # Verify at least some companies have VAT numbers
        companies_with_vat = [c for c in dataset.values() if c.vat_number]
        assert len(companies_with_vat) > 0
        logger.info(f"Dataset contains {len(companies_with_vat)} companies with VAT numbers")
        
        # Verify at least some companies have LEI codes
        companies_with_lei = [c for c in dataset.values() if c.lei_code]
        assert len(companies_with_lei) > 0
        logger.info(f"Dataset contains {len(companies_with_lei)} companies with LEI codes")
    
    @pytest.mark.asyncio
    async def test_dataset_validation(self, dataset_builder, validation_manager):
        """Test dataset validation functionality."""
        logger.info("Testing dataset validation")
        
        # Build a small dataset for testing
        dataset = await dataset_builder.build_comprehensive_dataset()
        
        # Limit to first 5 companies for faster testing
        test_dataset = dict(list(dataset.items())[:5])
        
        # Validate dataset
        validation_result = await validation_manager.validate_dataset(test_dataset)
        
        # Verify validation result structure
        assert 'session_id' in validation_result
        assert 'started_at' in validation_result
        assert 'completed_at' in validation_result
        assert 'statistics' in validation_result
        assert 'results' in validation_result
        
        # Verify statistics
        stats = validation_result['statistics']
        assert 'validated' in stats
        assert 'failed' in stats
        assert 'errors' in stats
        
        total_processed = stats['validated'] + stats['failed'] + stats['errors']
        assert total_processed == len(test_dataset)
        
        logger.info(f"Validation completed: {stats}")
        
        # Verify individual results
        for company_id, result in validation_result['results'].items():
            assert company_id in test_dataset
            assert 'status' in result
            assert 'validated_at' in result
            
            if 'validations' in result:
                for validation_type, validation_data in result['validations'].items():
                    assert validation_type in ['vat', 'lei']
                    assert 'valid' in validation_data
                    assert 'validated_at' in validation_data
    
    @pytest.mark.asyncio
    async def test_data_refresh_mechanism(self, dataset_builder, validation_manager):
        """Test data refresh mechanism."""
        logger.info("Testing data refresh mechanism")
        
        # Build dataset
        dataset = await dataset_builder.build_comprehensive_dataset()
        
        # Limit to first 3 companies for faster testing
        test_dataset = dict(list(dataset.items())[:3])
        
        # Make some data artificially stale
        for company in test_dataset.values():
            company.last_validated = datetime.utcnow() - timedelta(hours=25)  # Older than 24 hours
        
        # Refresh stale data
        refreshed_dataset = await validation_manager.refresh_stale_data(test_dataset)
        
        # Verify data was refreshed
        assert refreshed_dataset == test_dataset  # Same object reference
        
        # Check that validation timestamps were updated
        for company in test_dataset.values():
            if company.last_validated:
                age_hours = (datetime.utcnow() - company.last_validated).total_seconds() / 3600
                assert age_hours < 1  # Should be very recent
        
        logger.info("Data refresh mechanism working correctly")
    
    @pytest.mark.asyncio
    async def test_dataset_filtering(self, dataset_builder):
        """Test dataset filtering capabilities."""
        logger.info("Testing dataset filtering")
        
        # Build dataset
        dataset = await dataset_builder.build_comprehensive_dataset()
        
        # Test country filtering
        german_companies = dataset_builder.get_companies_by_criteria(countries=['DE'])
        assert all(c.country_code == 'DE' for c in german_companies)
        logger.info(f"Found {len(german_companies)} German companies")
        
        # Test industry filtering
        tech_companies = dataset_builder.get_companies_by_criteria(industries=['Technology'])
        assert all(c.industry == 'Technology' for c in tech_companies if c.industry)
        logger.info(f"Found {len(tech_companies)} technology companies")
        
        # Test size filtering
        large_companies = dataset_builder.get_companies_by_criteria(sizes=['Large'])
        assert all(c.size == 'Large' for c in large_companies if c.size)
        logger.info(f"Found {len(large_companies)} large companies")
        
        # Test validation status filtering
        valid_companies = dataset_builder.get_companies_by_criteria(validation_status=['VALID'])
        assert all(c.validation_status == 'VALID' for c in valid_companies)
        logger.info(f"Found {len(valid_companies)} fully validated companies")
        
        # Test limit
        limited_companies = dataset_builder.get_companies_by_criteria(limit=3)
        assert len(limited_companies) <= 3
        logger.info(f"Limited results to {len(limited_companies)} companies")
    
    @pytest.mark.asyncio
    async def test_validation_statistics(self, dataset_builder, validation_manager):
        """Test validation statistics generation."""
        logger.info("Testing validation statistics")
        
        # Build and validate dataset
        dataset = await dataset_builder.build_comprehensive_dataset()
        test_dataset = dict(list(dataset.items())[:3])
        
        await validation_manager.validate_dataset(test_dataset)
        
        # Get validation statistics
        stats = validation_manager.get_validation_statistics()
        
        # Verify statistics structure
        assert 'latest_session' in stats
        assert 'overall_statistics' in stats
        
        latest = stats['latest_session']
        assert 'session_id' in latest
        assert 'statistics' in latest
        
        overall = stats['overall_statistics']
        assert 'total_validation_sessions' in overall
        assert 'average_success_rate' in overall
        
        logger.info(f"Validation statistics: {overall}")
    
    @pytest.mark.asyncio
    async def test_data_quality_report(self, dataset_builder, validation_manager):
        """Test data quality report generation."""
        logger.info("Testing data quality report")
        
        # Build dataset
        dataset = await dataset_builder.build_comprehensive_dataset()
        
        # Generate quality report
        report = validation_manager.get_data_quality_report(dataset)
        
        # Verify report structure
        assert 'generated_at' in report
        assert 'total_companies' in report
        assert 'quality_metrics' in report
        assert 'validation_coverage' in report
        assert 'data_freshness' in report
        assert 'issues' in report
        
        # Verify quality metrics
        quality_metrics = report['quality_metrics']
        assert 'completeness' in quality_metrics
        
        completeness = quality_metrics['completeness']
        assert 'vat_number' in completeness
        assert 'lei_code' in completeness
        assert 'address' in completeness
        assert 'industry' in completeness
        
        # All completeness values should be between 0 and 1
        for metric, value in completeness.items():
            assert 0 <= value <= 1
        
        logger.info(f"Data quality report generated successfully")
        logger.info(f"Completeness metrics: {completeness}")
    
    @pytest.mark.asyncio
    async def test_dataset_persistence(self, dataset_builder):
        """Test dataset persistence and loading."""
        logger.info("Testing dataset persistence")
        
        # Build dataset
        original_dataset = await dataset_builder.build_comprehensive_dataset()
        original_count = len(original_dataset)
        
        # Save dataset (should happen automatically)
        await dataset_builder._save_comprehensive_dataset()
        
        # Create new builder instance
        config = ComprehensiveTestConfig.get_config()['data_manager']
        new_builder = ComprehensiveTestDatasetBuilder(config)
        await new_builder.initialize()
        
        try:
            # Load existing dataset
            await new_builder._load_existing_dataset()
            loaded_dataset = new_builder.comprehensive_dataset
            
            # Verify loaded dataset matches original
            assert len(loaded_dataset) == original_count
            
            # Verify some companies match
            for company_id in list(original_dataset.keys())[:3]:
                assert company_id in loaded_dataset
                original_company = original_dataset[company_id]
                loaded_company = loaded_dataset[company_id]
                
                assert original_company.name == loaded_company.name
                assert original_company.country_code == loaded_company.country_code
                assert original_company.vat_number == loaded_company.vat_number
            
            logger.info("Dataset persistence working correctly")
            
        finally:
            await new_builder.cleanup()
    
    def test_dataset_summary(self, dataset_builder):
        """Test dataset summary generation."""
        logger.info("Testing dataset summary")
        
        # Get summary (should work even with empty dataset)
        summary = dataset_builder.get_dataset_summary()
        
        # Verify summary structure
        assert isinstance(summary, dict)
        
        if 'error' not in summary:
            assert 'total_companies' in summary
            assert 'countries' in summary
            assert 'industries' in summary
            
            logger.info(f"Dataset summary: {summary}")
        else:
            logger.info(f"No dataset available: {summary['error']}")


# Standalone test functions for manual testing
async def test_full_dataset_workflow():
    """Test complete dataset workflow."""
    logger.info("Starting full dataset workflow test")
    
    config = ComprehensiveTestConfig.get_config()['data_manager']
    
    # Initialize components
    builder = ComprehensiveTestDatasetBuilder(config)
    validator = DataValidationRefreshManager(config)
    
    try:
        await builder.initialize()
        await validator.initialize()
        
        # Step 1: Build comprehensive dataset
        logger.info("Step 1: Building comprehensive dataset")
        dataset = await builder.build_comprehensive_dataset()
        logger.info(f"Built dataset with {len(dataset)} companies")
        
        # Step 2: Validate dataset
        logger.info("Step 2: Validating dataset")
        validation_result = await validator.validate_dataset(dataset)
        logger.info(f"Validation completed: {validation_result['statistics']}")
        
        # Step 3: Generate quality report
        logger.info("Step 3: Generating quality report")
        quality_report = validator.get_data_quality_report(dataset)
        logger.info(f"Quality report generated with {len(quality_report.get('issues', []))} issues")
        
        # Step 4: Test filtering
        logger.info("Step 4: Testing filtering capabilities")
        german_companies = builder.get_companies_by_criteria(countries=['DE'], limit=5)
        logger.info(f"Found {len(german_companies)} German companies")
        
        tech_companies = builder.get_companies_by_criteria(industries=['Technology'], limit=5)
        logger.info(f"Found {len(tech_companies)} technology companies")
        
        # Step 5: Test refresh mechanism
        logger.info("Step 5: Testing refresh mechanism")
        refreshed_dataset = await validator.refresh_stale_data(dataset)
        logger.info("Data refresh completed")
        
        logger.info("✅ Full dataset workflow test completed successfully")
        
    except Exception as e:
        logger.error(f"❌ Full dataset workflow test failed: {str(e)}")
        raise
    
    finally:
        await builder.cleanup()
        await validator.cleanup()


async def demo_dataset_capabilities():
    """Demonstrate dataset capabilities."""
    logger.info("Demonstrating comprehensive dataset capabilities")
    
    config = ComprehensiveTestConfig.get_config()['data_manager']
    builder = ComprehensiveTestDatasetBuilder(config)
    
    try:
        await builder.initialize()
        
        # Build dataset
        dataset = await builder.build_comprehensive_dataset()
        
        # Show summary
        summary = builder.get_dataset_summary()
        print("\n" + "="*60)
        print("COMPREHENSIVE TEST DATASET SUMMARY")
        print("="*60)
        print(f"Total Companies: {summary.get('total_companies', 0)}")
        print(f"Countries: {', '.join(summary.get('countries', []))}")
        print(f"Industries: {', '.join(summary.get('industries', []))}")
        
        validation_stats = summary.get('validation_stats', {})
        if validation_stats:
            print(f"Companies with VAT: {validation_stats.get('with_vat', 0)}")
            print(f"Companies with LEI: {validation_stats.get('with_lei', 0)}")
            print(f"Fully Validated: {validation_stats.get('fully_validated', 0)}")
        
        # Show some example companies
        print("\nEXAMPLE COMPANIES:")
        print("-" * 40)
        
        example_companies = list(dataset.values())[:5]
        for company in example_companies:
            print(f"• {company.name} ({company.country_code})")
            print(f"  Industry: {company.industry or 'N/A'}")
            print(f"  VAT: {company.vat_number or 'N/A'}")
            print(f"  LEI: {company.lei_code or 'N/A'}")
            print(f"  Status: {company.validation_status}")
            print()
        
        print("="*60)
        print("Dataset ready for comprehensive testing!")
        print("="*60)
        
    finally:
        await builder.cleanup()


if __name__ == '__main__':
    # Run demonstration
    asyncio.run(demo_dataset_capabilities())
    
    # Run full workflow test
    asyncio.run(test_full_dataset_workflow())