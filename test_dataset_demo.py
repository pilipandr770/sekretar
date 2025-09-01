"""
Simple demonstration of the comprehensive test dataset system.
"""
import asyncio
import sys
import os
import logging

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tests.infrastructure.config import ComprehensiveTestConfig
from tests.infrastructure.test_dataset_builder import ComprehensiveTestDatasetBuilder
from tests.infrastructure.data_validation_refresh import DataValidationRefreshManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


async def demo_dataset_system():
    """Demonstrate the comprehensive test dataset system."""
    logger.info("Starting comprehensive test dataset demonstration")
    
    # Get configuration
    config = ComprehensiveTestConfig.get_config()['data_manager']
    
    # Initialize components
    builder = ComprehensiveTestDatasetBuilder(config)
    validator = DataValidationRefreshManager(config)
    
    try:
        # Initialize
        logger.info("Initializing dataset builder and validator...")
        await builder.initialize()
        await validator.initialize()
        
        # Step 1: Build comprehensive dataset
        logger.info("Step 1: Building comprehensive test dataset...")
        dataset = await builder.build_comprehensive_dataset()
        logger.info(f"✅ Built dataset with {len(dataset)} companies")
        
        # Step 2: Show dataset summary
        logger.info("Step 2: Generating dataset summary...")
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
        
        # Step 3: Show example companies
        print("\nEXAMPLE COMPANIES:")
        print("-" * 40)
        
        example_companies = list(dataset.values())[:5]
        for company in example_companies:
            print(f"• {company.name} ({company.country_code})")
            print(f"  Industry: {company.industry or 'N/A'}")
            print(f"  VAT: {company.vat_number or 'N/A'}")
            print(f"  LEI: {company.lei_code or 'N/A'}")
            print(f"  Status: {company.validation_status}")
            
            # Show validation details if available
            vat_validation = company.additional_data.get('vat_validation', {})
            lei_validation = company.additional_data.get('lei_validation', {})
            
            if vat_validation:
                vat_valid = "✅" if vat_validation.get('valid', False) else "❌"
                print(f"  VAT Validation: {vat_valid}")
            
            if lei_validation:
                lei_valid = "✅" if lei_validation.get('valid', False) else "❌"
                print(f"  LEI Validation: {lei_valid}")
            
            print()
        
        # Step 4: Test filtering capabilities
        logger.info("Step 3: Testing filtering capabilities...")
        
        # Filter by country
        german_companies = builder.get_companies_by_criteria(countries=['DE'], limit=3)
        print(f"German companies found: {len(german_companies)}")
        for company in german_companies:
            print(f"  • {company.name}")
        
        # Filter by industry
        tech_companies = builder.get_companies_by_criteria(industries=['Technology'], limit=3)
        print(f"Technology companies found: {len(tech_companies)}")
        for company in tech_companies:
            print(f"  • {company.name}")
        
        # Step 5: Validate a subset of the dataset
        logger.info("Step 4: Validating subset of dataset...")
        test_dataset = dict(list(dataset.items())[:3])  # First 3 companies
        
        validation_result = await validator.validate_dataset(test_dataset)
        print(f"\nValidation Results:")
        print(f"  Session ID: {validation_result['session_id']}")
        print(f"  Duration: {validation_result.get('duration_seconds', 0):.1f} seconds")
        
        stats = validation_result['statistics']
        print(f"  Validated: {stats['validated']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Errors: {stats['errors']}")
        
        # Step 6: Generate quality report
        logger.info("Step 5: Generating data quality report...")
        quality_report = validator.get_data_quality_report(dataset)
        
        print(f"\nData Quality Report:")
        print(f"  Generated: {quality_report['generated_at']}")
        
        completeness = quality_report.get('quality_metrics', {}).get('completeness', {})
        if completeness:
            print(f"  VAT Number Completeness: {completeness.get('vat_number', 0):.1%}")
            print(f"  LEI Code Completeness: {completeness.get('lei_code', 0):.1%}")
            print(f"  Address Completeness: {completeness.get('address', 0):.1%}")
            print(f"  Industry Completeness: {completeness.get('industry', 0):.1%}")
        
        issues = quality_report.get('issues', [])
        if issues:
            print(f"  Issues Found: {len(issues)}")
            for issue in issues[:3]:  # Show first 3 issues
                print(f"    • [{issue.get('severity', 'unknown').upper()}] {issue.get('description', 'No description')}")
        else:
            print("  ✅ No quality issues found")
        
        print("\n" + "="*60)
        print("✅ COMPREHENSIVE TEST DATASET READY FOR TESTING!")
        print("="*60)
        print("\nThe dataset includes:")
        print("• Real company data from multiple EU countries")
        print("• Validated VAT numbers and LEI codes")
        print("• Mix of industries and company sizes")
        print("• Comprehensive validation and quality metrics")
        print("• Filtering and selection capabilities")
        print("\nUse this dataset for comprehensive system testing!")
        
    except Exception as e:
        logger.error(f"❌ Demo failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        # Cleanup
        logger.info("Cleaning up resources...")
        await builder.cleanup()
        await validator.cleanup()
    
    return 0


if __name__ == '__main__':
    try:
        result = asyncio.run(demo_dataset_system())
        sys.exit(result)
    except KeyboardInterrupt:
        print("\n❌ Demo cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        sys.exit(1)