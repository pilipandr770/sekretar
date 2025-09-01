"""
Comprehensive Test Dataset CLI

Command-line interface for managing the comprehensive test dataset.
"""
import asyncio
import argparse
import json
import sys
from datetime import datetime
from typing import Dict, Any

from tests.infrastructure.config import ComprehensiveTestConfig
from tests.infrastructure.test_dataset_builder import ComprehensiveTestDatasetBuilder
from tests.infrastructure.data_validation_refresh import DataValidationRefreshManager


class DatasetCLI:
    """Command-line interface for dataset management."""
    
    def __init__(self):
        """Initialize dataset CLI."""
        self.config = ComprehensiveTestConfig.get_config()
        self.dataset_builder = None
        self.validation_manager = None
    
    async def initialize(self):
        """Initialize CLI components."""
        self.dataset_builder = ComprehensiveTestDatasetBuilder(self.config['data_manager'])
        self.validation_manager = DataValidationRefreshManager(self.config['data_manager'])
        
        await self.dataset_builder.initialize()
        await self.validation_manager.initialize()
    
    async def build_dataset(self, args):
        """Build comprehensive test dataset."""
        print("Building comprehensive test dataset...")
        
        try:
            dataset = await self.dataset_builder.build_comprehensive_dataset()
            
            print(f"✅ Successfully built dataset with {len(dataset)} companies")
            
            # Print summary
            summary = self.dataset_builder.get_dataset_summary()
            print("\nDataset Summary:")
            print(f"  Total companies: {summary['total_companies']}")
            print(f"  Countries: {', '.join(summary['countries'])}")
            print(f"  Industries: {', '.join(summary['industries'])}")
            
            validation_stats = summary.get('validation_stats', {})
            if validation_stats:
                print(f"  Companies with VAT: {validation_stats.get('with_vat', 0)}")
                print(f"  Companies with LEI: {validation_stats.get('with_lei', 0)}")
                print(f"  Fully validated: {validation_stats.get('fully_validated', 0)}")
            
        except Exception as e:
            print(f"❌ Failed to build dataset: {str(e)}")
            return 1
        
        return 0
    
    async def validate_dataset(self, args):
        """Validate existing dataset."""
        print("Validating test dataset...")
        
        try:
            # Load existing dataset
            dataset = self.dataset_builder.comprehensive_dataset
            if not dataset:
                print("❌ No dataset found. Please build dataset first.")
                return 1
            
            # Perform validation
            validation_result = await self.validation_manager.validate_dataset(dataset)
            
            print(f"✅ Validation completed")
            print(f"  Session ID: {validation_result['session_id']}")
            print(f"  Duration: {validation_result['duration_seconds']:.1f} seconds")
            
            stats = validation_result['statistics']
            print(f"  Validated: {stats['validated']}")
            print(f"  Failed: {stats['failed']}")
            print(f"  Errors: {stats['errors']}")
            
            if args.detailed:
                print("\nDetailed Results:")
                for company_id, result in validation_result['results'].items():
                    status = result.get('status', 'unknown')
                    print(f"  {company_id}: {status}")
                    if result.get('validations'):
                        for val_type, val_result in result['validations'].items():
                            valid = val_result.get('valid', False)
                            print(f"    {val_type}: {'✅' if valid else '❌'}")
            
        except Exception as e:
            print(f"❌ Failed to validate dataset: {str(e)}")
            return 1
        
        return 0
    
    async def refresh_dataset(self, args):
        """Refresh stale data in dataset."""
        print("Refreshing stale data...")
        
        try:
            # Load existing dataset
            dataset = self.dataset_builder.comprehensive_dataset
            if not dataset:
                print("❌ No dataset found. Please build dataset first.")
                return 1
            
            # Refresh stale data
            refreshed_dataset = await self.validation_manager.refresh_stale_data(dataset)
            
            print("✅ Data refresh completed")
            
            # Retry failed validations if requested
            if args.retry_failed:
                print("Retrying failed validations...")
                retry_results = await self.validation_manager.retry_failed_validations(refreshed_dataset)
                print(f"  Retried: {retry_results['retried']}")
                print(f"  Succeeded: {retry_results['succeeded']}")
                print(f"  Still failed: {retry_results['still_failed']}")
            
        except Exception as e:
            print(f"❌ Failed to refresh dataset: {str(e)}")
            return 1
        
        return 0
    
    async def show_summary(self, args):
        """Show dataset summary."""
        try:
            summary = self.dataset_builder.get_dataset_summary()
            
            if 'error' in summary:
                print(f"❌ {summary['error']}")
                return 1
            
            print("Dataset Summary")
            print("=" * 50)
            print(f"Total companies: {summary['total_companies']}")
            print(f"Countries: {', '.join(summary['countries'])}")
            print(f"Industries: {', '.join(summary['industries'])}")
            
            if summary.get('generated_at'):
                print(f"Generated at: {summary['generated_at']}")
                if summary.get('age_hours'):
                    print(f"Age: {summary['age_hours']:.1f} hours")
            
            validation_stats = summary.get('validation_stats', {})
            if validation_stats:
                print("\nValidation Statistics:")
                print(f"  Companies with VAT: {validation_stats.get('with_vat', 0)}")
                print(f"  Companies with LEI: {validation_stats.get('with_lei', 0)}")
                print(f"  VAT valid: {validation_stats.get('vat_valid', 0)}")
                print(f"  LEI valid: {validation_stats.get('lei_valid', 0)}")
                print(f"  Fully validated: {validation_stats.get('fully_validated', 0)}")
            
        except Exception as e:
            print(f"❌ Failed to show summary: {str(e)}")
            return 1
        
        return 0
    
    async def show_validation_stats(self, args):
        """Show validation statistics."""
        try:
            stats = self.validation_manager.get_validation_statistics()
            
            if 'error' in stats:
                print(f"❌ {stats['error']}")
                return 1
            
            print("Validation Statistics")
            print("=" * 50)
            
            latest = stats.get('latest_session', {})
            if latest:
                print(f"Latest Session: {latest.get('session_id', 'N/A')}")
                print(f"Completed: {latest.get('completed_at', 'N/A')}")
                print(f"Duration: {latest.get('duration_seconds', 0):.1f} seconds")
                
                session_stats = latest.get('statistics', {})
                print(f"Results: {session_stats.get('validated', 0)} validated, {session_stats.get('failed', 0)} failed")
            
            overall = stats.get('overall_statistics', {})
            if overall:
                print(f"\nOverall Statistics:")
                print(f"  Total sessions: {overall.get('total_validation_sessions', 0)}")
                print(f"  Total validations: {overall.get('total_validations_performed', 0)}")
                print(f"  Current failures: {overall.get('current_failed_validations', 0)}")
                print(f"  Average success rate: {overall.get('average_success_rate', 0):.1%}")
            
            failed = stats.get('failed_validations', [])
            if failed and args.show_failures:
                print(f"\nFailed Validations ({len(failed)}):")
                for failure in failed[:10]:  # Show first 10
                    print(f"  {failure['company_id']}: {', '.join(failure['failed_types'])} (attempts: {failure['attempts']})")
                
                if len(failed) > 10:
                    print(f"  ... and {len(failed) - 10} more")
            
        except Exception as e:
            print(f"❌ Failed to show validation statistics: {str(e)}")
            return 1
        
        return 0
    
    async def show_quality_report(self, args):
        """Show data quality report."""
        try:
            # Load existing dataset
            dataset = self.dataset_builder.comprehensive_dataset
            if not dataset:
                print("❌ No dataset found. Please build dataset first.")
                return 1
            
            report = self.validation_manager.get_data_quality_report(dataset)
            
            print("Data Quality Report")
            print("=" * 50)
            print(f"Generated: {report['generated_at']}")
            print(f"Total companies: {report['total_companies']}")
            
            # Quality metrics
            quality = report.get('quality_metrics', {}).get('completeness', {})
            if quality:
                print("\nData Completeness:")
                print(f"  VAT numbers: {quality.get('vat_number', 0):.1%}")
                print(f"  LEI codes: {quality.get('lei_code', 0):.1%}")
                print(f"  Addresses: {quality.get('address', 0):.1%}")
                print(f"  Industries: {quality.get('industry', 0):.1%}")
            
            # Validation coverage
            validation = report.get('validation_coverage', {})
            if validation:
                print("\nValidation Coverage:")
                print(f"  VAT validation coverage: {validation.get('vat_validation_coverage', 0):.1%}")
                print(f"  LEI validation coverage: {validation.get('lei_validation_coverage', 0):.1%}")
                print(f"  VAT success rate: {validation.get('vat_validation_success_rate', 0):.1%}")
                print(f"  LEI success rate: {validation.get('lei_validation_success_rate', 0):.1%}")
            
            # Data freshness
            freshness = report.get('data_freshness', {})
            if freshness:
                print("\nData Freshness:")
                print(f"  Fresh data: {freshness.get('fresh_data_percentage', 0):.1%}")
                print(f"  Stale data: {freshness.get('stale_data_percentage', 0):.1%}")
                print(f"  No validation: {freshness.get('no_validation_percentage', 0):.1%}")
            
            # Issues
            issues = report.get('issues', [])
            if issues:
                print(f"\nIssues Found ({len(issues)}):")
                for issue in issues:
                    severity = issue.get('severity', 'unknown').upper()
                    print(f"  [{severity}] {issue.get('description', 'No description')}")
            else:
                print("\n✅ No issues found")
            
        except Exception as e:
            print(f"❌ Failed to generate quality report: {str(e)}")
            return 1
        
        return 0
    
    async def list_companies(self, args):
        """List companies in dataset with filtering."""
        try:
            # Load existing dataset
            dataset = self.dataset_builder.comprehensive_dataset
            if not dataset:
                print("❌ No dataset found. Please build dataset first.")
                return 1
            
            # Apply filters
            companies = self.dataset_builder.get_companies_by_criteria(
                countries=args.countries.split(',') if args.countries else None,
                industries=args.industries.split(',') if args.industries else None,
                sizes=args.sizes.split(',') if args.sizes else None,
                validation_status=args.validation_status.split(',') if args.validation_status else None,
                limit=args.limit
            )
            
            print(f"Companies ({len(companies)} found)")
            print("=" * 80)
            
            for company in companies:
                print(f"{company.name}")
                print(f"  Country: {company.country_code}")
                print(f"  Industry: {company.industry or 'N/A'}")
                print(f"  Size: {company.size or 'N/A'}")
                print(f"  VAT: {company.vat_number or 'N/A'}")
                print(f"  LEI: {company.lei_code or 'N/A'}")
                print(f"  Status: {company.validation_status}")
                
                if args.show_validation:
                    vat_val = company.additional_data.get('vat_validation', {})
                    lei_val = company.additional_data.get('lei_validation', {})
                    
                    if vat_val:
                        print(f"  VAT Valid: {'✅' if vat_val.get('valid') else '❌'}")
                    if lei_val:
                        print(f"  LEI Valid: {'✅' if lei_val.get('valid') else '❌'}")
                
                print()
            
        except Exception as e:
            print(f"❌ Failed to list companies: {str(e)}")
            return 1
        
        return 0
    
    async def export_dataset(self, args):
        """Export dataset to file."""
        try:
            # Load existing dataset
            dataset = self.dataset_builder.comprehensive_dataset
            if not dataset:
                print("❌ No dataset found. Please build dataset first.")
                return 1
            
            # Prepare export data
            export_data = {
                'exported_at': datetime.utcnow().isoformat(),
                'total_companies': len(dataset),
                'companies': []
            }
            
            for company_id, company in dataset.items():
                company_dict = {
                    'id': company_id,
                    'name': company.name,
                    'vat_number': company.vat_number,
                    'lei_code': company.lei_code,
                    'country_code': company.country_code,
                    'address': company.address,
                    'industry': company.industry,
                    'size': company.size,
                    'validation_status': company.validation_status,
                    'last_validated': company.last_validated.isoformat() if company.last_validated else None
                }
                
                if args.include_validation_details:
                    company_dict['validation_details'] = company.additional_data
                
                export_data['companies'].append(company_dict)
            
            # Write to file
            with open(args.output_file, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            print(f"✅ Dataset exported to {args.output_file}")
            print(f"  {len(dataset)} companies exported")
            
        except Exception as e:
            print(f"❌ Failed to export dataset: {str(e)}")
            return 1
        
        return 0
    
    async def cleanup(self):
        """Cleanup CLI resources."""
        if self.dataset_builder:
            await self.dataset_builder.cleanup()
        
        if self.validation_manager:
            await self.validation_manager.cleanup()


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description='Comprehensive Test Dataset Management CLI')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Build dataset command
    build_parser = subparsers.add_parser('build', help='Build comprehensive test dataset')
    
    # Validate dataset command
    validate_parser = subparsers.add_parser('validate', help='Validate existing dataset')
    validate_parser.add_argument('--detailed', action='store_true', help='Show detailed validation results')
    
    # Refresh dataset command
    refresh_parser = subparsers.add_parser('refresh', help='Refresh stale data in dataset')
    refresh_parser.add_argument('--retry-failed', action='store_true', help='Retry failed validations')
    
    # Summary command
    summary_parser = subparsers.add_parser('summary', help='Show dataset summary')
    
    # Validation statistics command
    stats_parser = subparsers.add_parser('stats', help='Show validation statistics')
    stats_parser.add_argument('--show-failures', action='store_true', help='Show failed validations')
    
    # Quality report command
    quality_parser = subparsers.add_parser('quality', help='Show data quality report')
    
    # List companies command
    list_parser = subparsers.add_parser('list', help='List companies in dataset')
    list_parser.add_argument('--countries', help='Filter by countries (comma-separated)')
    list_parser.add_argument('--industries', help='Filter by industries (comma-separated)')
    list_parser.add_argument('--sizes', help='Filter by company sizes (comma-separated)')
    list_parser.add_argument('--validation-status', help='Filter by validation status (comma-separated)')
    list_parser.add_argument('--limit', type=int, help='Limit number of results')
    list_parser.add_argument('--show-validation', action='store_true', help='Show validation details')
    
    # Export command
    export_parser = subparsers.add_parser('export', help='Export dataset to file')
    export_parser.add_argument('output_file', help='Output file path')
    export_parser.add_argument('--include-validation-details', action='store_true', help='Include validation details')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    # Run CLI
    cli = DatasetCLI()
    
    async def run_command():
        try:
            await cli.initialize()
            
            if args.command == 'build':
                return await cli.build_dataset(args)
            elif args.command == 'validate':
                return await cli.validate_dataset(args)
            elif args.command == 'refresh':
                return await cli.refresh_dataset(args)
            elif args.command == 'summary':
                return await cli.show_summary(args)
            elif args.command == 'stats':
                return await cli.show_validation_stats(args)
            elif args.command == 'quality':
                return await cli.show_quality_report(args)
            elif args.command == 'list':
                return await cli.list_companies(args)
            elif args.command == 'export':
                return await cli.export_dataset(args)
            else:
                print(f"❌ Unknown command: {args.command}")
                return 1
        
        finally:
            await cli.cleanup()
    
    try:
        return asyncio.run(run_command())
    except KeyboardInterrupt:
        print("\n❌ Operation cancelled by user")
        return 1
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        return 1


if __name__ == '__main__':
    sys.exit(main())