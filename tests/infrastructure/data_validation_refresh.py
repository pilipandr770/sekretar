"""
Data Validation and Refresh Mechanisms

Provides automated validation and refresh capabilities for test dataset.
"""
import asyncio
import logging
import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import asdict

from tests.infrastructure.models import CompanyData
from tests.infrastructure.test_data_manager import TestDataManager


class DataValidationRefreshManager:
    """
    Manages validation and refresh of test company data.
    
    Features:
    - Automated data validation scheduling
    - Incremental refresh of stale data
    - Data quality monitoring
    - Validation result tracking
    - Error handling and retry logic
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize data validation and refresh manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Initialize test data manager
        self.data_manager = TestDataManager(config)
        
        # Validation configuration
        self.validation_config = {
            'vat_validation_interval_hours': config.get('vat_validation_interval_hours', 24),
            'lei_validation_interval_hours': config.get('lei_validation_interval_hours', 168),  # Weekly
            'max_validation_age_hours': config.get('max_validation_age_hours', 72),
            'batch_size': config.get('validation_batch_size', 10),
            'retry_failed_validations': config.get('retry_failed_validations', True),
            'max_retry_attempts': config.get('max_retry_attempts', 3),
            'validation_timeout_seconds': config.get('validation_timeout_seconds', 30)
        }
        
        # Tracking
        self.validation_history: List[Dict[str, Any]] = []
        self.failed_validations: Dict[str, Dict[str, Any]] = {}
        self.validation_stats: Dict[str, Any] = {}
        
    async def initialize(self):
        """Initialize the validation and refresh manager."""
        self.logger.info("Initializing data validation and refresh manager")
        
        await self.data_manager.initialize()
        
        # Load validation history if available
        await self._load_validation_history()
        
        self.logger.info("Data validation and refresh manager initialized")
    
    async def validate_dataset(self, dataset: Dict[str, CompanyData]) -> Dict[str, Any]:
        """
        Validate entire dataset and return validation results.
        
        Args:
            dataset: Dictionary of company data to validate
            
        Returns:
            Dict containing validation results and statistics
        """
        self.logger.info(f"Starting validation of {len(dataset)} companies")
        
        validation_session = {
            'session_id': f"validation_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
            'started_at': datetime.utcnow(),
            'total_companies': len(dataset),
            'results': {},
            'statistics': {
                'validated': 0,
                'failed': 0,
                'skipped': 0,
                'errors': 0
            }
        }
        
        # Process companies in batches
        company_items = list(dataset.items())
        batch_size = self.validation_config['batch_size']
        
        for i in range(0, len(company_items), batch_size):
            batch = company_items[i:i + batch_size]
            batch_results = await self._validate_batch(batch)
            
            # Update session results
            validation_session['results'].update(batch_results)
            
            # Update statistics
            for result in batch_results.values():
                status = result.get('status', 'error')
                if status in validation_session['statistics']:
                    validation_session['statistics'][status] += 1
            
            # Rate limiting between batches
            await asyncio.sleep(1)
        
        validation_session['completed_at'] = datetime.utcnow()
        validation_session['duration_seconds'] = (
            validation_session['completed_at'] - validation_session['started_at']
        ).total_seconds()
        
        # Save validation session
        self.validation_history.append(validation_session)
        await self._save_validation_history()
        
        self.logger.info(f"Dataset validation completed: {validation_session['statistics']}")
        
        return validation_session
    
    async def _validate_batch(self, batch: List[Tuple[str, CompanyData]]) -> Dict[str, Dict[str, Any]]:
        """Validate a batch of companies."""
        batch_results = {}
        
        for company_id, company_data in batch:
            try:
                result = await self._validate_single_company(company_id, company_data)
                batch_results[company_id] = result
                
            except Exception as e:
                self.logger.error(f"Error validating company {company_id}: {str(e)}")
                batch_results[company_id] = {
                    'status': 'error',
                    'error': str(e),
                    'validated_at': datetime.utcnow().isoformat()
                }
        
        return batch_results
    
    async def _validate_single_company(self, company_id: str, company_data: CompanyData) -> Dict[str, Any]:
        """Validate a single company's data."""
        validation_result = {
            'company_id': company_id,
            'company_name': company_data.name,
            'status': 'validated',
            'validations': {},
            'validated_at': datetime.utcnow().isoformat(),
            'needs_refresh': False
        }
        
        # Check if validation is needed based on age
        needs_vat_validation = self._needs_validation(
            company_data, 'vat_validation', self.validation_config['vat_validation_interval_hours']
        )
        needs_lei_validation = self._needs_validation(
            company_data, 'lei_validation', self.validation_config['lei_validation_interval_hours']
        )
        
        # Validate VAT number if needed
        if company_data.vat_number and needs_vat_validation:
            try:
                vat_result = await self.data_manager._validate_vat_number(
                    company_data.vat_number, company_data.country_code
                )
                validation_result['validations']['vat'] = vat_result
                
                # Update company data
                company_data.additional_data['vat_validation'] = vat_result
                
            except Exception as e:
                validation_result['validations']['vat'] = {
                    'valid': False,
                    'error': str(e),
                    'validated_at': datetime.utcnow().isoformat()
                }
        
        # Validate LEI code if needed
        if company_data.lei_code and needs_lei_validation:
            try:
                lei_result = await self.data_manager._validate_lei_code(company_data.lei_code)
                validation_result['validations']['lei'] = lei_result
                
                # Update company data
                company_data.additional_data['lei_validation'] = lei_result
                
            except Exception as e:
                validation_result['validations']['lei'] = {
                    'valid': False,
                    'error': str(e),
                    'validated_at': datetime.utcnow().isoformat()
                }
        
        # Update overall validation status
        company_data.validation_status = self.data_manager._determine_validation_status(company_data)
        company_data.last_validated = datetime.utcnow()
        
        # Check if any validations failed
        failed_validations = []
        for validation_type, result in validation_result['validations'].items():
            if not result.get('valid', False):
                failed_validations.append(validation_type)
        
        if failed_validations:
            validation_result['status'] = 'failed'
            validation_result['failed_validations'] = failed_validations
            
            # Track failed validation for retry
            self.failed_validations[company_id] = {
                'company_data': company_data,
                'failed_validations': failed_validations,
                'attempts': 1,
                'last_attempt': datetime.utcnow(),
                'max_attempts': self.validation_config['max_retry_attempts']
            }
        
        return validation_result
    
    def _needs_validation(self, company_data: CompanyData, validation_type: str, interval_hours: int) -> bool:
        """Check if a specific validation is needed based on age."""
        validation_data = company_data.additional_data.get(validation_type, {})
        
        if not validation_data:
            return True  # No previous validation
        
        validated_at_str = validation_data.get('validated_at')
        if not validated_at_str:
            return True  # No validation timestamp
        
        try:
            validated_at = datetime.fromisoformat(validated_at_str.replace('Z', '+00:00'))
            age_hours = (datetime.utcnow() - validated_at).total_seconds() / 3600
            return age_hours > interval_hours
        except (ValueError, TypeError):
            return True  # Invalid timestamp, re-validate
    
    async def refresh_stale_data(self, dataset: Dict[str, CompanyData]) -> Dict[str, CompanyData]:
        """
        Refresh stale data in the dataset.
        
        Args:
            dataset: Dictionary of company data to check and refresh
            
        Returns:
            Updated dataset with refreshed data
        """
        self.logger.info("Checking for stale data to refresh")
        
        stale_companies = []
        max_age_hours = self.validation_config['max_validation_age_hours']
        
        for company_id, company_data in dataset.items():
            if self._is_data_stale(company_data, max_age_hours):
                stale_companies.append((company_id, company_data))
        
        if not stale_companies:
            self.logger.info("No stale data found")
            return dataset
        
        self.logger.info(f"Found {len(stale_companies)} companies with stale data")
        
        # Refresh stale companies
        refreshed_count = 0
        for company_id, company_data in stale_companies:
            try:
                await self._refresh_company_data(company_id, company_data)
                refreshed_count += 1
                
                # Rate limiting
                await asyncio.sleep(0.5)
                
            except Exception as e:
                self.logger.error(f"Failed to refresh data for {company_id}: {str(e)}")
        
        self.logger.info(f"Refreshed data for {refreshed_count} companies")
        return dataset
    
    def _is_data_stale(self, company_data: CompanyData, max_age_hours: int) -> bool:
        """Check if company data is stale."""
        if not company_data.last_validated:
            return True
        
        age_hours = (datetime.utcnow() - company_data.last_validated).total_seconds() / 3600
        return age_hours > max_age_hours
    
    async def _refresh_company_data(self, company_id: str, company_data: CompanyData):
        """Refresh data for a single company."""
        self.logger.debug(f"Refreshing data for company {company_id}")
        
        # Re-validate VAT number
        if company_data.vat_number:
            try:
                vat_result = await self.data_manager._validate_vat_number(
                    company_data.vat_number, company_data.country_code
                )
                company_data.additional_data['vat_validation'] = vat_result
            except Exception as e:
                self.logger.warning(f"VAT validation failed for {company_id}: {str(e)}")
        
        # Re-validate LEI code
        if company_data.lei_code:
            try:
                lei_result = await self.data_manager._validate_lei_code(company_data.lei_code)
                company_data.additional_data['lei_validation'] = lei_result
            except Exception as e:
                self.logger.warning(f"LEI validation failed for {company_id}: {str(e)}")
        
        # Update validation status and timestamp
        company_data.validation_status = self.data_manager._determine_validation_status(company_data)
        company_data.last_validated = datetime.utcnow()
    
    async def retry_failed_validations(self, dataset: Dict[str, CompanyData]) -> Dict[str, Any]:
        """Retry failed validations with exponential backoff."""
        if not self.validation_config['retry_failed_validations']:
            return {'retried': 0, 'succeeded': 0, 'still_failed': 0}
        
        self.logger.info(f"Retrying {len(self.failed_validations)} failed validations")
        
        retry_results = {
            'retried': 0,
            'succeeded': 0,
            'still_failed': 0,
            'details': []
        }
        
        for company_id, failure_info in list(self.failed_validations.items()):
            if failure_info['attempts'] >= failure_info['max_attempts']:
                continue  # Max attempts reached
            
            # Check if enough time has passed for retry (exponential backoff)
            backoff_hours = 2 ** (failure_info['attempts'] - 1)  # 1, 2, 4, 8 hours
            time_since_last = datetime.utcnow() - failure_info['last_attempt']
            
            if time_since_last < timedelta(hours=backoff_hours):
                continue  # Not enough time passed
            
            # Retry validation
            try:
                company_data = failure_info['company_data']
                result = await self._validate_single_company(company_id, company_data)
                
                retry_results['retried'] += 1
                failure_info['attempts'] += 1
                failure_info['last_attempt'] = datetime.utcnow()
                
                if result['status'] == 'validated':
                    # Success - remove from failed validations
                    del self.failed_validations[company_id]
                    retry_results['succeeded'] += 1
                    retry_results['details'].append({
                        'company_id': company_id,
                        'status': 'succeeded',
                        'attempts': failure_info['attempts']
                    })
                else:
                    retry_results['still_failed'] += 1
                    retry_results['details'].append({
                        'company_id': company_id,
                        'status': 'still_failed',
                        'attempts': failure_info['attempts']
                    })
                
                # Rate limiting
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Retry failed for {company_id}: {str(e)}")
                failure_info['attempts'] += 1
                failure_info['last_attempt'] = datetime.utcnow()
                retry_results['still_failed'] += 1
        
        self.logger.info(f"Retry results: {retry_results['succeeded']} succeeded, {retry_results['still_failed']} still failed")
        return retry_results
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get comprehensive validation statistics."""
        if not self.validation_history:
            return {'error': 'No validation history available'}
        
        latest_session = self.validation_history[-1]
        
        # Calculate overall statistics
        total_validations = sum(len(session['results']) for session in self.validation_history)
        total_failures = len(self.failed_validations)
        
        # Success rate over time
        success_rates = []
        for session in self.validation_history[-10:]:  # Last 10 sessions
            stats = session['statistics']
            total = stats.get('validated', 0) + stats.get('failed', 0)
            if total > 0:
                success_rate = stats.get('validated', 0) / total
                success_rates.append(success_rate)
        
        avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
        
        return {
            'latest_session': {
                'session_id': latest_session['session_id'],
                'completed_at': latest_session.get('completed_at'),
                'statistics': latest_session['statistics'],
                'duration_seconds': latest_session.get('duration_seconds')
            },
            'overall_statistics': {
                'total_validation_sessions': len(self.validation_history),
                'total_validations_performed': total_validations,
                'current_failed_validations': total_failures,
                'average_success_rate': avg_success_rate
            },
            'failed_validations': [
                {
                    'company_id': company_id,
                    'failed_types': info['failed_validations'],
                    'attempts': info['attempts'],
                    'last_attempt': info['last_attempt'].isoformat()
                }
                for company_id, info in self.failed_validations.items()
            ]
        }
    
    def get_data_quality_report(self, dataset: Dict[str, CompanyData]) -> Dict[str, Any]:
        """Generate comprehensive data quality report."""
        report = {
            'generated_at': datetime.utcnow().isoformat(),
            'total_companies': len(dataset),
            'quality_metrics': {},
            'validation_coverage': {},
            'data_freshness': {},
            'issues': []
        }
        
        # Quality metrics
        companies_with_vat = sum(1 for c in dataset.values() if c.vat_number)
        companies_with_lei = sum(1 for c in dataset.values() if c.lei_code)
        companies_with_address = sum(1 for c in dataset.values() if c.address)
        companies_with_industry = sum(1 for c in dataset.values() if c.industry)
        
        report['quality_metrics'] = {
            'completeness': {
                'vat_number': companies_with_vat / len(dataset),
                'lei_code': companies_with_lei / len(dataset),
                'address': companies_with_address / len(dataset),
                'industry': companies_with_industry / len(dataset)
            }
        }
        
        # Validation coverage
        vat_validated = 0
        lei_validated = 0
        vat_valid = 0
        lei_valid = 0
        
        for company in dataset.values():
            vat_validation = company.additional_data.get('vat_validation', {})
            lei_validation = company.additional_data.get('lei_validation', {})
            
            if vat_validation:
                vat_validated += 1
                if vat_validation.get('valid', False):
                    vat_valid += 1
            
            if lei_validation:
                lei_validated += 1
                if lei_validation.get('valid', False):
                    lei_valid += 1
        
        report['validation_coverage'] = {
            'vat_validation_coverage': vat_validated / companies_with_vat if companies_with_vat > 0 else 0,
            'lei_validation_coverage': lei_validated / companies_with_lei if companies_with_lei > 0 else 0,
            'vat_validation_success_rate': vat_valid / vat_validated if vat_validated > 0 else 0,
            'lei_validation_success_rate': lei_valid / lei_validated if lei_validated > 0 else 0
        }
        
        # Data freshness
        now = datetime.utcnow()
        fresh_data = 0
        stale_data = 0
        no_validation = 0
        
        for company in dataset.values():
            if company.last_validated:
                age_hours = (now - company.last_validated).total_seconds() / 3600
                if age_hours <= self.validation_config['max_validation_age_hours']:
                    fresh_data += 1
                else:
                    stale_data += 1
            else:
                no_validation += 1
        
        report['data_freshness'] = {
            'fresh_data_percentage': fresh_data / len(dataset),
            'stale_data_percentage': stale_data / len(dataset),
            'no_validation_percentage': no_validation / len(dataset)
        }
        
        # Identify issues
        if report['validation_coverage']['vat_validation_success_rate'] < 0.8:
            report['issues'].append({
                'type': 'low_vat_validation_success',
                'severity': 'medium',
                'description': f"VAT validation success rate is {report['validation_coverage']['vat_validation_success_rate']:.1%}"
            })
        
        if report['data_freshness']['stale_data_percentage'] > 0.2:
            report['issues'].append({
                'type': 'high_stale_data',
                'severity': 'medium',
                'description': f"{report['data_freshness']['stale_data_percentage']:.1%} of data is stale"
            })
        
        if len(self.failed_validations) > len(dataset) * 0.1:
            report['issues'].append({
                'type': 'high_failed_validations',
                'severity': 'high',
                'description': f"{len(self.failed_validations)} companies have failed validations"
            })
        
        return report
    
    async def _load_validation_history(self):
        """Load validation history from file."""
        history_file = 'validation_history.json'
        
        try:
            if os.path.exists(history_file):
                with open(history_file, 'r') as f:
                    data = json.load(f)
                
                self.validation_history = data.get('validation_history', [])
                
                # Convert datetime strings back to datetime objects for failed validations
                failed_validations = data.get('failed_validations', {})
                for company_id, info in failed_validations.items():
                    if info.get('last_attempt'):
                        info['last_attempt'] = datetime.fromisoformat(info['last_attempt'])
                    # Note: company_data would need to be reconstructed from dataset
                
                self.logger.info(f"Loaded validation history with {len(self.validation_history)} sessions")
                
        except Exception as e:
            self.logger.warning(f"Failed to load validation history: {str(e)}")
    
    async def _save_validation_history(self):
        """Save validation history to file."""
        history_file = 'validation_history.json'
        
        try:
            # Prepare data for JSON serialization
            history_data = []
            for session in self.validation_history:
                session_copy = session.copy()
                # Convert datetime objects to strings
                if session_copy.get('started_at'):
                    session_copy['started_at'] = session_copy['started_at'].isoformat()
                if session_copy.get('completed_at'):
                    session_copy['completed_at'] = session_copy['completed_at'].isoformat()
                history_data.append(session_copy)
            
            # Prepare failed validations (without company_data objects)
            failed_validations_data = {}
            for company_id, info in self.failed_validations.items():
                info_copy = info.copy()
                info_copy.pop('company_data', None)  # Remove company_data object
                if info_copy.get('last_attempt'):
                    info_copy['last_attempt'] = info_copy['last_attempt'].isoformat()
                failed_validations_data[company_id] = info_copy
            
            data = {
                'validation_history': history_data,
                'failed_validations': failed_validations_data
            }
            
            with open(history_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.debug("Saved validation history")
            
        except Exception as e:
            self.logger.error(f"Failed to save validation history: {str(e)}")
    
    async def cleanup(self):
        """Cleanup resources."""
        self.logger.info("Cleaning up data validation and refresh manager")
        
        if self.data_manager:
            await self.data_manager.cleanup()
        
        # Save final validation history
        await self._save_validation_history()
        
        self.logger.info("Data validation and refresh manager cleanup completed")