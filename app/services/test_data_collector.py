"""Test data collection service for comprehensive system testing."""
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog
from dataclasses import dataclass, asdict
import json
import random

from .kyb_adapters.vies import VIESAdapter
from .kyb_adapters.gleif import GLEIFAdapter
from .kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded

logger = structlog.get_logger()


@dataclass
class CompanyTestData:
    """Data structure for test company information."""
    name: str
    country_code: str
    vat_number: Optional[str] = None
    lei_code: Optional[str] = None
    address: Optional[str] = None
    company_type: str = "unknown"  # large_corp, sme, startup
    industry: Optional[str] = None
    validation_status: Dict[str, str] = None
    last_validated: Optional[datetime] = None
    
    def __post_init__(self):
        if self.validation_status is None:
            self.validation_status = {}


@dataclass
class ValidationResult:
    """Result of data validation."""
    identifier: str
    source: str
    status: str  # valid, invalid, error, not_found
    valid: bool
    data: Dict[str, Any]
    response_time_ms: int
    error: Optional[str] = None
    cached: bool = False


class TestDataCollector:
    """Enhanced data collector for comprehensive testing with real company data."""
    
    def __init__(self, redis_client=None):
        """Initialize test data collector."""
        self.redis_client = redis_client
        self.vies_adapter = VIESAdapter(redis_client)
        self.gleif_adapter = GLEIFAdapter(redis_client)
        
        # Configuration for test data collection
        self.batch_size = 10
        self.max_concurrent_requests = 5
        self.request_delay = 1.0  # seconds between requests
        self.validation_cache_ttl = 86400  # 24 hours
        
        logger.info("Test data collector initialized")
    
    def collect_vies_test_data(self, 
                              country_codes: List[str] = None, 
                              sample_size: int = 50,
                              **kwargs) -> List[CompanyTestData]:
        """
        Collect real VAT numbers from VIES for testing.
        
        Args:
            country_codes: List of EU country codes to collect from
            sample_size: Number of companies to collect per country
            **kwargs: Additional options:
                - include_invalid: Include known invalid VAT numbers (default: False)
                - timeout: Request timeout (default: 15)
                - force_refresh: Skip cache (default: False)
        
        Returns:
            List of CompanyTestData with validated VAT information
        """
        if country_codes is None:
            # Focus on major EU countries for testing
            country_codes = ['DE', 'FR', 'IT', 'ES', 'NL', 'BE', 'AT', 'IE', 'PL', 'SE']
        
        include_invalid = kwargs.get('include_invalid', False)
        timeout = kwargs.get('timeout', 15)
        force_refresh = kwargs.get('force_refresh', False)
        
        logger.info("Starting VIES test data collection", 
                   countries=country_codes, 
                   sample_size=sample_size)
        
        all_test_data = []
        
        for country_code in country_codes:
            try:
                country_data = self._collect_country_vat_data(
                    country_code, 
                    sample_size, 
                    include_invalid=include_invalid,
                    timeout=timeout,
                    force_refresh=force_refresh
                )
                all_test_data.extend(country_data)
                
                # Add delay between countries to respect rate limits
                if len(country_codes) > 1:
                    time.sleep(self.request_delay)
                    
            except Exception as e:
                logger.error("Failed to collect data for country", 
                           country=country_code, error=str(e))
                continue
        
        logger.info("VIES test data collection completed", 
                   total_companies=len(all_test_data),
                   countries_processed=len(country_codes))
        
        return all_test_data
    
    def collect_gleif_test_data(self, 
                               country_codes: List[str] = None,
                               sample_size: int = 50,
                               **kwargs) -> List[CompanyTestData]:
        """
        Collect real LEI codes from GLEIF for testing.
        
        Args:
            country_codes: List of country codes to collect from
            sample_size: Number of companies to collect per country
            **kwargs: Additional options:
                - include_inactive: Include inactive LEI codes (default: True)
                - timeout: Request timeout (default: 15)
                - force_refresh: Skip cache (default: False)
        
        Returns:
            List of CompanyTestData with validated LEI information
        """
        if country_codes is None:
            # Focus on major countries with LEI adoption
            country_codes = ['US', 'GB', 'DE', 'FR', 'JP', 'CA', 'AU', 'IT', 'ES', 'NL']
        
        include_inactive = kwargs.get('include_inactive', True)
        timeout = kwargs.get('timeout', 15)
        force_refresh = kwargs.get('force_refresh', False)
        
        logger.info("Starting GLEIF test data collection", 
                   countries=country_codes, 
                   sample_size=sample_size)
        
        all_test_data = []
        
        for country_code in country_codes:
            try:
                country_data = self._collect_country_lei_data(
                    country_code,
                    sample_size,
                    include_inactive=include_inactive,
                    timeout=timeout,
                    force_refresh=force_refresh
                )
                all_test_data.extend(country_data)
                
                # Add delay between countries to respect rate limits
                if len(country_codes) > 1:
                    time.sleep(self.request_delay * 0.5)  # GLEIF allows higher rates
                    
            except Exception as e:
                logger.error("Failed to collect LEI data for country", 
                           country=country_code, error=str(e))
                continue
        
        logger.info("GLEIF test data collection completed", 
                   total_companies=len(all_test_data),
                   countries_processed=len(country_codes))
        
        return all_test_data
    
    def validate_batch_vat_numbers(self, 
                                  vat_numbers: List[str],
                                  **kwargs) -> List[ValidationResult]:
        """
        Validate a batch of VAT numbers with enhanced error handling.
        
        Args:
            vat_numbers: List of VAT numbers to validate
            **kwargs: Validation options
        
        Returns:
            List of ValidationResult objects
        """
        if not vat_numbers:
            return []
        
        logger.info("Starting batch VAT validation", count=len(vat_numbers))
        
        # Configure batch processing
        batch_delay = kwargs.get('batch_delay', 1.0)
        max_workers = min(kwargs.get('max_workers', 3), 5)
        timeout = kwargs.get('timeout', 15)
        
        results = []
        
        # Process in batches to manage rate limits
        for i in range(0, len(vat_numbers), self.batch_size):
            batch = vat_numbers[i:i + self.batch_size]
            
            try:
                batch_results = self.vies_adapter.check_batch(
                    batch,
                    batch_delay=batch_delay,
                    max_workers=max_workers,
                    timeout=timeout
                )
                
                # Convert to ValidationResult objects
                for result in batch_results:
                    validation_result = ValidationResult(
                        identifier=result.get('identifier', ''),
                        source='VIES',
                        status=result.get('status', 'error'),
                        valid=result.get('valid', False),
                        data=result.get('data', {}),
                        response_time_ms=result.get('response_time_ms', 0),
                        error=result.get('error'),
                        cached=result.get('cached', False)
                    )
                    results.append(validation_result)
                
                # Add delay between batches
                if i + self.batch_size < len(vat_numbers):
                    time.sleep(batch_delay * 2)
                    
            except Exception as e:
                logger.error("Batch VAT validation failed", 
                           batch_start=i, error=str(e))
                
                # Create error results for the batch
                for vat_number in batch:
                    error_result = ValidationResult(
                        identifier=vat_number,
                        source='VIES',
                        status='error',
                        valid=False,
                        data={},
                        response_time_ms=0,
                        error=f"Batch processing failed: {str(e)}"
                    )
                    results.append(error_result)
        
        logger.info("Batch VAT validation completed", 
                   total=len(results),
                   valid=len([r for r in results if r.valid]),
                   errors=len([r for r in results if r.status == 'error']))
        
        return results
    
    def validate_batch_lei_codes(self, 
                                lei_codes: List[str],
                                **kwargs) -> List[ValidationResult]:
        """
        Validate a batch of LEI codes with enhanced error handling.
        
        Args:
            lei_codes: List of LEI codes to validate
            **kwargs: Validation options
        
        Returns:
            List of ValidationResult objects
        """
        if not lei_codes:
            return []
        
        logger.info("Starting batch LEI validation", count=len(lei_codes))
        
        # Configure batch processing
        batch_delay = kwargs.get('batch_delay', 0.5)
        max_workers = min(kwargs.get('max_workers', 5), 8)
        timeout = kwargs.get('timeout', 15)
        include_relationships = kwargs.get('include_relationships', False)
        
        results = []
        
        # Process in batches
        for i in range(0, len(lei_codes), self.batch_size):
            batch = lei_codes[i:i + self.batch_size]
            
            try:
                batch_results = self.gleif_adapter.check_batch(
                    batch,
                    batch_delay=batch_delay,
                    max_workers=max_workers,
                    timeout=timeout,
                    include_relationships=include_relationships
                )
                
                # Convert to ValidationResult objects
                for result in batch_results:
                    validation_result = ValidationResult(
                        identifier=result.get('identifier', ''),
                        source='GLEIF',
                        status=result.get('status', 'error'),
                        valid=result.get('valid', False),
                        data=result.get('data', {}),
                        response_time_ms=result.get('response_time_ms', 0),
                        error=result.get('error'),
                        cached=result.get('cached', False)
                    )
                    results.append(validation_result)
                
                # Add delay between batches
                if i + self.batch_size < len(lei_codes):
                    time.sleep(batch_delay)
                    
            except Exception as e:
                logger.error("Batch LEI validation failed", 
                           batch_start=i, error=str(e))
                
                # Create error results for the batch
                for lei_code in batch:
                    error_result = ValidationResult(
                        identifier=lei_code,
                        source='GLEIF',
                        status='error',
                        valid=False,
                        data={},
                        response_time_ms=0,
                        error=f"Batch processing failed: {str(e)}"
                    )
                    results.append(error_result)
        
        logger.info("Batch LEI validation completed", 
                   total=len(results),
                   valid=len([r for r in results if r.valid]),
                   errors=len([r for r in results if r.status == 'error']))
        
        return results
    
    def _collect_country_vat_data(self, 
                                 country_code: str, 
                                 sample_size: int,
                                 **kwargs) -> List[CompanyTestData]:
        """Collect VAT data for a specific country."""
        # Known valid VAT numbers for testing (publicly available)
        known_vat_numbers = self._get_known_vat_numbers(country_code)
        
        test_data = []
        
        # Validate known VAT numbers
        for vat_info in known_vat_numbers[:sample_size]:
            try:
                result = self.vies_adapter.check_single(
                    vat_info['vat_number'], 
                    country_code,
                    timeout=kwargs.get('timeout', 15),
                    force_refresh=kwargs.get('force_refresh', False)
                )
                
                if result['status'] in ['valid', 'invalid']:
                    company_data = CompanyTestData(
                        name=result.get('company_name', vat_info.get('name', 'Unknown')),
                        country_code=country_code,
                        vat_number=vat_info['vat_number'],
                        address=result.get('company_address'),
                        company_type=vat_info.get('type', 'unknown'),
                        industry=vat_info.get('industry'),
                        validation_status={'vies': result['status']},
                        last_validated=datetime.utcnow()
                    )
                    test_data.append(company_data)
                
                # Add delay between requests
                time.sleep(self.request_delay)
                
            except Exception as e:
                logger.warning("Failed to validate VAT number", 
                             vat_number=vat_info['vat_number'], 
                             error=str(e))
                continue
        
        return test_data
    
    def _collect_country_lei_data(self, 
                                 country_code: str, 
                                 sample_size: int,
                                 **kwargs) -> List[CompanyTestData]:
        """Collect LEI data for a specific country."""
        # Known valid LEI codes for testing (publicly available)
        known_lei_codes = self._get_known_lei_codes(country_code)
        
        test_data = []
        
        # Validate known LEI codes
        for lei_info in known_lei_codes[:sample_size]:
            try:
                result = self.gleif_adapter.check_single(
                    lei_info['lei_code'],
                    timeout=kwargs.get('timeout', 15),
                    force_refresh=kwargs.get('force_refresh', False),
                    include_relationships=False
                )
                
                if result['status'] in ['valid', 'not_found']:
                    company_data = CompanyTestData(
                        name=result.get('legal_name', lei_info.get('name', 'Unknown')),
                        country_code=country_code,
                        lei_code=lei_info['lei_code'],
                        address=result.get('legal_address'),
                        company_type=lei_info.get('type', 'unknown'),
                        industry=lei_info.get('industry'),
                        validation_status={'gleif': result['status']},
                        last_validated=datetime.utcnow()
                    )
                    test_data.append(company_data)
                
                # Add delay between requests
                time.sleep(self.request_delay * 0.5)
                
            except Exception as e:
                logger.warning("Failed to validate LEI code", 
                             lei_code=lei_info['lei_code'], 
                             error=str(e))
                continue
        
        return test_data
    
    def _get_known_vat_numbers(self, country_code: str) -> List[Dict[str, Any]]:
        """Get known valid VAT numbers for testing (publicly available data)."""
        # This would typically come from a curated dataset
        # For now, return a sample of known public companies
        known_companies = {
            'DE': [
                {'vat_number': 'DE143593636', 'name': 'SAP SE', 'type': 'large_corp', 'industry': 'Software'},
                {'vat_number': 'DE811334915', 'name': 'Siemens AG', 'type': 'large_corp', 'industry': 'Industrial'},
                {'vat_number': 'DE129273398', 'name': 'BMW AG', 'type': 'large_corp', 'industry': 'Automotive'},
            ],
            'FR': [
                {'vat_number': 'FR76542065479', 'name': 'Total SE', 'type': 'large_corp', 'industry': 'Energy'},
                {'vat_number': 'FR55542107651', 'name': 'LVMH', 'type': 'large_corp', 'industry': 'Luxury'},
            ],
            'NL': [
                {'vat_number': 'NL009291477B01', 'name': 'ASML Holding NV', 'type': 'large_corp', 'industry': 'Technology'},
                {'vat_number': 'NL007994701B01', 'name': 'Royal Dutch Shell', 'type': 'large_corp', 'industry': 'Energy'},
            ],
            'IE': [
                {'vat_number': 'IE9825613N', 'name': 'Microsoft Ireland Operations Limited', 'type': 'large_corp', 'industry': 'Technology'},
                {'vat_number': 'IE6388047V', 'name': 'Google Ireland Limited', 'type': 'large_corp', 'industry': 'Technology'},
            ]
        }
        
        return known_companies.get(country_code, [])
    
    def _get_known_lei_codes(self, country_code: str) -> List[Dict[str, Any]]:
        """Get known valid LEI codes for testing (publicly available data)."""
        known_companies = {
            'US': [
                {'lei_code': '549300DTUYXVMJXZNY75', 'name': 'Apple Inc.', 'type': 'large_corp', 'industry': 'Technology'},
                {'lei_code': '549300E9PC51EN656011', 'name': 'Microsoft Corporation', 'type': 'large_corp', 'industry': 'Technology'},
                {'lei_code': '549300SRLRVTR996F086', 'name': 'Amazon.com Inc.', 'type': 'large_corp', 'industry': 'E-commerce'},
            ],
            'GB': [
                {'lei_code': '549300BFXFJ6KBNTKY86', 'name': 'Unilever PLC', 'type': 'large_corp', 'industry': 'Consumer Goods'},
                {'lei_code': '213800LBQA1Y9L22JB70', 'name': 'BP p.l.c.', 'type': 'large_corp', 'industry': 'Energy'},
            ],
            'DE': [
                {'lei_code': '529900T8BM49AURSDO55', 'name': 'SAP SE', 'type': 'large_corp', 'industry': 'Software'},
                {'lei_code': '549300MARJXVVQNRQZ33', 'name': 'Siemens AG', 'type': 'large_corp', 'industry': 'Industrial'},
            ]
        }
        
        return known_companies.get(country_code, [])
    
    def build_comprehensive_test_dataset(self, 
                                       **kwargs) -> Dict[str, List[CompanyTestData]]:
        """
        Build a comprehensive test dataset with companies from multiple sources.
        
        Args:
            **kwargs: Configuration options:
                - vat_countries: List of EU countries for VAT data
                - lei_countries: List of countries for LEI data
                - sample_size_per_country: Number of companies per country
                - include_mixed_data: Include companies with both VAT and LEI
                - force_refresh: Skip all caches
        
        Returns:
            Dict with categorized test data
        """
        vat_countries = kwargs.get('vat_countries', ['DE', 'FR', 'NL', 'IE'])
        lei_countries = kwargs.get('lei_countries', ['US', 'GB', 'DE', 'FR'])
        sample_size = kwargs.get('sample_size_per_country', 10)
        include_mixed = kwargs.get('include_mixed_data', True)
        force_refresh = kwargs.get('force_refresh', False)
        
        logger.info("Building comprehensive test dataset", 
                   vat_countries=vat_countries,
                   lei_countries=lei_countries,
                   sample_size=sample_size)
        
        dataset = {
            'vat_only': [],
            'lei_only': [],
            'mixed_data': [],
            'validation_errors': []
        }
        
        # Collect VAT data
        try:
            vat_data = self.collect_vies_test_data(
                country_codes=vat_countries,
                sample_size=sample_size,
                force_refresh=force_refresh
            )
            dataset['vat_only'] = vat_data
        except Exception as e:
            logger.error("Failed to collect VAT data", error=str(e))
        
        # Collect LEI data
        try:
            lei_data = self.collect_gleif_test_data(
                country_codes=lei_countries,
                sample_size=sample_size,
                force_refresh=force_refresh
            )
            dataset['lei_only'] = lei_data
        except Exception as e:
            logger.error("Failed to collect LEI data", error=str(e))
        
        # Create mixed data (companies with both VAT and LEI)
        if include_mixed:
            try:
                mixed_data = self._create_mixed_test_data(
                    sample_size=min(sample_size, 5),
                    force_refresh=force_refresh
                )
                dataset['mixed_data'] = mixed_data
            except Exception as e:
                logger.error("Failed to create mixed data", error=str(e))
        
        # Log dataset statistics
        total_companies = sum(len(companies) for companies in dataset.values())
        logger.info("Comprehensive test dataset built", 
                   total_companies=total_companies,
                   vat_only=len(dataset['vat_only']),
                   lei_only=len(dataset['lei_only']),
                   mixed_data=len(dataset['mixed_data']))
        
        return dataset
    
    def _create_mixed_test_data(self, 
                               sample_size: int = 5,
                               force_refresh: bool = False) -> List[CompanyTestData]:
        """Create test data for companies with both VAT and LEI codes."""
        # Known companies with both VAT and LEI (publicly available)
        mixed_companies = [
            {
                'name': 'SAP SE',
                'country_code': 'DE',
                'vat_number': 'DE143593636',
                'lei_code': '529900T8BM49AURSDO55',
                'type': 'large_corp',
                'industry': 'Software'
            },
            {
                'name': 'Siemens AG',
                'country_code': 'DE',
                'vat_number': 'DE811334915',
                'lei_code': '549300MARJXVVQNRQZ33',
                'type': 'large_corp',
                'industry': 'Industrial'
            }
        ]
        
        test_data = []
        
        for company_info in mixed_companies[:sample_size]:
            try:
                # Validate both VAT and LEI
                vat_result = self.vies_adapter.check_single(
                    company_info['vat_number'],
                    company_info['country_code'],
                    force_refresh=force_refresh
                )
                
                time.sleep(self.request_delay)
                
                lei_result = self.gleif_adapter.check_single(
                    company_info['lei_code'],
                    force_refresh=force_refresh
                )
                
                # Create combined test data
                company_data = CompanyTestData(
                    name=company_info['name'],
                    country_code=company_info['country_code'],
                    vat_number=company_info['vat_number'],
                    lei_code=company_info['lei_code'],
                    address=vat_result.get('company_address') or lei_result.get('legal_address'),
                    company_type=company_info['type'],
                    industry=company_info['industry'],
                    validation_status={
                        'vies': vat_result.get('status', 'error'),
                        'gleif': lei_result.get('status', 'error')
                    },
                    last_validated=datetime.utcnow()
                )
                
                test_data.append(company_data)
                
                time.sleep(self.request_delay)
                
            except Exception as e:
                logger.warning("Failed to create mixed test data", 
                             company=company_info['name'], 
                             error=str(e))
                continue
        
        return test_data
    
    def refresh_test_dataset(self, 
                           dataset: Dict[str, List[CompanyTestData]],
                           max_age_hours: int = 24) -> Dict[str, List[CompanyTestData]]:
        """
        Refresh test dataset by re-validating stale data.
        
        Args:
            dataset: Existing test dataset
            max_age_hours: Maximum age before refresh is needed
        
        Returns:
            Refreshed dataset
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        refreshed_dataset = {}
        
        for category, companies in dataset.items():
            refreshed_companies = []
            
            for company in companies:
                needs_refresh = (
                    company.last_validated is None or 
                    company.last_validated < cutoff_time
                )
                
                if needs_refresh:
                    try:
                        refreshed_company = self._refresh_company_data(company)
                        refreshed_companies.append(refreshed_company)
                    except Exception as e:
                        logger.warning("Failed to refresh company data", 
                                     company=company.name, error=str(e))
                        # Keep original data if refresh fails
                        refreshed_companies.append(company)
                else:
                    refreshed_companies.append(company)
            
            refreshed_dataset[category] = refreshed_companies
        
        return refreshed_dataset
    
    def _refresh_company_data(self, company: CompanyTestData) -> CompanyTestData:
        """Refresh validation data for a single company."""
        validation_status = {}
        
        # Refresh VAT validation if available
        if company.vat_number:
            try:
                vat_result = self.vies_adapter.check_single(
                    company.vat_number,
                    company.country_code,
                    force_refresh=True
                )
                validation_status['vies'] = vat_result.get('status', 'error')
                
                # Update company name and address if available
                if vat_result.get('company_name'):
                    company.name = vat_result['company_name']
                if vat_result.get('company_address'):
                    company.address = vat_result['company_address']
                    
            except Exception as e:
                logger.warning("Failed to refresh VAT data", 
                             vat_number=company.vat_number, error=str(e))
                validation_status['vies'] = 'error'
        
        # Refresh LEI validation if available
        if company.lei_code:
            try:
                lei_result = self.gleif_adapter.check_single(
                    company.lei_code,
                    force_refresh=True
                )
                validation_status['gleif'] = lei_result.get('status', 'error')
                
                # Update company name and address if available
                if lei_result.get('legal_name'):
                    company.name = lei_result['legal_name']
                if lei_result.get('legal_address') and not company.address:
                    company.address = lei_result['legal_address']
                    
            except Exception as e:
                logger.warning("Failed to refresh LEI data", 
                             lei_code=company.lei_code, error=str(e))
                validation_status['gleif'] = 'error'
        
        # Update validation status and timestamp
        company.validation_status = validation_status
        company.last_validated = datetime.utcnow()
        
        return company
    
    def export_test_dataset(self, 
                           dataset: Dict[str, List[CompanyTestData]], 
                           format: str = 'json') -> str:
        """
        Export test dataset to specified format.
        
        Args:
            dataset: Test dataset to export
            format: Export format ('json', 'csv')
        
        Returns:
            Serialized dataset
        """
        if format.lower() == 'json':
            # Convert dataclasses to dicts for JSON serialization
            json_dataset = {}
            for category, companies in dataset.items():
                json_dataset[category] = [
                    {
                        **asdict(company),
                        'last_validated': company.last_validated.isoformat() if company.last_validated else None
                    }
                    for company in companies
                ]
            
            return json.dumps(json_dataset, indent=2, default=str)
        
        elif format.lower() == 'csv':
            # Flatten all companies into CSV format
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write header
            writer.writerow([
                'category', 'name', 'country_code', 'vat_number', 'lei_code',
                'address', 'company_type', 'industry', 'validation_status',
                'last_validated'
            ])
            
            # Write data
            for category, companies in dataset.items():
                for company in companies:
                    writer.writerow([
                        category,
                        company.name,
                        company.country_code,
                        company.vat_number or '',
                        company.lei_code or '',
                        company.address or '',
                        company.company_type,
                        company.industry or '',
                        json.dumps(company.validation_status),
                        company.last_validated.isoformat() if company.last_validated else ''
                    ])
            
            return output.getvalue()
        
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """Get statistics about data collection performance."""
        vies_stats = self.vies_adapter.get_stats()
        gleif_stats = self.gleif_adapter.get_stats()
        
        return {
            'vies_adapter': vies_stats,
            'gleif_adapter': gleif_stats,
            'configuration': {
                'batch_size': self.batch_size,
                'max_concurrent_requests': self.max_concurrent_requests,
                'request_delay': self.request_delay,
                'validation_cache_ttl': self.validation_cache_ttl
            }
        }