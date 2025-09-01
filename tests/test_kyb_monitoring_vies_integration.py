"""
Comprehensive VIES integration tests for KYB monitoring system.

This test suite validates VIES integration using real company data from the test dataset.
Tests cover VAT number validation, batch processing, error handling, and monitoring workflows.
"""
import pytest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, List, Any

from app import create_app, db
from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, KYBAlert, KYBMonitoringConfig
from app.services.kyb_adapters.vies import VIESAdapter
from app.services.kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded
from tests.conftest import TestConfig


class TestVIESIntegrationKYB:
    """Test VIES integration with real company data for KYB monitoring."""
    
    @pytest.fixture(scope='class')
    def app(self):
        """Create test application."""
        app = create_app(TestConfig)
        with app.app_context():
            db.create_all()
            yield app
            db.drop_all()
    
    @pytest.fixture
    def client(self, app):
        """Create test client."""
        return app.test_client()
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.incr.return_value = 1
        redis_mock.keys.return_value = []
        redis_mock.delete.return_value = 1
        return redis_mock
    
    @pytest.fixture
    def vies_adapter(self, mock_redis):
        """Create VIES adapter with mocked Redis."""
        return VIESAdapter(redis_client=mock_redis)
    
    @pytest.fixture
    def real_company_data(self):
        """Load real company data from test dataset."""
        try:
            with open('comprehensive_test_dataset.json', 'r', encoding='utf-8') as f:
                dataset = json.load(f)
            return dataset['companies']
        except FileNotFoundError:
            # Fallback to minimal test data if dataset not available
            return {
                "sap_germany": {
                    "name": "SAP SE",
                    "vat_number": "DE143593636",
                    "country_code": "DE",
                    "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
                    "industry": "Technology"
                },
                "microsoft_ireland": {
                    "name": "Microsoft Ireland Operations Limited",
                    "vat_number": "IE9825613N",
                    "country_code": "IE",
                    "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18"
                }
            }
    
    @pytest.fixture
    def test_tenant(self, app):
        """Create test tenant with KYB monitoring config."""
        from app.models.tenancy import Tenant
        from app.models.auth import User
        
        with app.app_context():
            # Create tenant
            tenant = Tenant(
                name="Test Company",
                domain="test.com",
                status="active"
            )
            db.session.add(tenant)
            db.session.flush()
            
            # Create user
            user = User(
                email="test@test.com",
                full_name="Test User",
                tenant_id=tenant.id
            )
            user.set_password("password123")
            db.session.add(user)
            
            # Create KYB monitoring config
            config = KYBMonitoringConfig(
                tenant_id=tenant.id,
                vies_enabled=True,
                default_check_frequency='daily',
                alert_on_vat_invalid=True
            )
            db.session.add(config)
            db.session.commit()
            
            yield tenant
            
            # Cleanup
            db.session.delete(config)
            db.session.delete(user)
            db.session.delete(tenant)
            db.session.commit()


class TestVIESRealDataValidation(TestVIESIntegrationKYB):
    """Test VIES validation with real company VAT numbers."""
    
    def test_validate_real_german_vat_numbers(self, vies_adapter, real_company_data):
        """Test validation of real German VAT numbers."""
        german_companies = {k: v for k, v in real_company_data.items() 
                          if v.get('country_code') == 'DE'}
        
        assert len(german_companies) > 0, "No German companies in test data"
        
        for company_key, company in german_companies.items():
            vat_number = company['vat_number']
            
            # Test VAT format validation
            format_result = vies_adapter.validate_vat_format(vat_number)
            assert format_result['valid'] is True, f"Invalid VAT format for {company['name']}: {vat_number}"
            assert format_result['country_code'] == 'DE'
            
            # Test parsing
            country, parsed_vat = vies_adapter._parse_vat_number(vat_number)
            assert country == 'DE'
            assert len(parsed_vat) == 9, f"German VAT should be 9 digits, got {len(parsed_vat)} for {vat_number}"
    
    def test_validate_real_irish_vat_numbers(self, vies_adapter, real_company_data):
        """Test validation of real Irish VAT numbers."""
        irish_companies = {k: v for k, v in real_company_data.items() 
                         if v.get('country_code') == 'IE'}
        
        if len(irish_companies) == 0:
            pytest.skip("No Irish companies in test data")
        
        for company_key, company in irish_companies.items():
            vat_number = company['vat_number']
            
            # Test VAT format validation
            format_result = vies_adapter.validate_vat_format(vat_number)
            assert format_result['valid'] is True, f"Invalid VAT format for {company['name']}: {vat_number}"
            assert format_result['country_code'] == 'IE'
    
    def test_validate_real_french_vat_numbers(self, vies_adapter, real_company_data):
        """Test validation of real French VAT numbers."""
        french_companies = {k: v for k, v in real_company_data.items() 
                          if v.get('country_code') == 'FR'}
        
        if len(french_companies) == 0:
            pytest.skip("No French companies in test data")
        
        for company_key, company in french_companies.items():
            vat_number = company['vat_number']
            
            # Test VAT format validation
            format_result = vies_adapter.validate_vat_format(vat_number)
            assert format_result['valid'] is True, f"Invalid VAT format for {company['name']}: {vat_number}"
            assert format_result['country_code'] == 'FR'
    
    @patch('requests.Session.post')
    def test_vies_api_call_with_real_data(self, mock_post, vies_adapter, real_company_data):
        """Test actual VIES API calls with real company data."""
        # Mock successful VIES response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                    <countryCode>DE</countryCode>
                    <vatNumber>143593636</vatNumber>
                    <requestDate>2025-01-01</requestDate>
                    <valid>true</valid>
                    <name>SAP SE</name>
                    <address>DIETMAR-HOPP-ALLEE 16 69190 WALLDORF</address>
                </checkVatResponse>
            </soap:Body>
        </soap:Envelope>'''
        mock_post.return_value = mock_response
        
        # Test with first company from dataset
        first_company = next(iter(real_company_data.values()))
        vat_number = first_company['vat_number']
        
        result = vies_adapter.check_single(vat_number)
        
        # Verify result structure
        assert 'status' in result
        assert 'valid' in result
        assert 'identifier' in result
        assert 'source' in result
        assert result['source'] == 'VIES'
        assert 'checked_at' in result
        assert 'response_time_ms' in result
        
        # Verify API was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert 'checkVat' in call_args[1]['data']


class TestVIESBatchProcessing(TestVIESIntegrationKYB):
    """Test VIES batch processing with real company data."""
    
    @patch('requests.Session.post')
    def test_batch_validation_real_companies(self, mock_post, vies_adapter, real_company_data):
        """Test batch validation of real company VAT numbers."""
        # Mock successful responses for all requests
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                    <countryCode>DE</countryCode>
                    <vatNumber>143593636</vatNumber>
                    <requestDate>2025-01-01</requestDate>
                    <valid>true</valid>
                    <name>TEST COMPANY</name>
                    <address>TEST ADDRESS</address>
                </checkVatResponse>
            </soap:Body>
        </soap:Envelope>'''
        mock_post.return_value = mock_response
        
        # Get VAT numbers from real companies
        vat_numbers = [company['vat_number'] for company in real_company_data.values() 
                      if 'vat_number' in company][:5]  # Limit to 5 for testing
        
        assert len(vat_numbers) > 0, "No VAT numbers found in test data"
        
        # Test batch processing
        results = vies_adapter.check_batch(vat_numbers, batch_delay=0.1)
        
        # Verify results
        assert len(results) == len(vat_numbers)
        for i, result in enumerate(results):
            assert result['identifier'] == vat_numbers[i]
            assert 'status' in result
            assert 'source' in result
            assert result['source'] == 'VIES'
        
        # Verify API was called for each VAT number
        assert mock_post.call_count == len(vat_numbers)
    
    def test_batch_processing_with_mixed_countries(self, vies_adapter, real_company_data):
        """Test batch processing with VAT numbers from different countries."""
        # Group companies by country
        countries = {}
        for company in real_company_data.values():
            country = company.get('country_code')
            if country and 'vat_number' in company:
                if country not in countries:
                    countries[country] = []
                countries[country].append(company['vat_number'])
        
        # Create mixed batch with one VAT from each country
        mixed_batch = []
        for country, vat_numbers in countries.items():
            if vat_numbers:
                mixed_batch.append(vat_numbers[0])
        
        assert len(mixed_batch) > 1, "Need multiple countries for this test"
        
        # Test format validation for mixed batch
        for vat_number in mixed_batch:
            format_result = vies_adapter.validate_vat_format(vat_number)
            assert format_result['valid'] is True, f"Invalid format: {vat_number}"
    
    def test_batch_processing_performance_metrics(self, vies_adapter, real_company_data):
        """Test batch processing performance with real data."""
        vat_numbers = [company['vat_number'] for company in real_company_data.values() 
                      if 'vat_number' in company][:3]  # Small batch for testing
        
        start_time = time.time()
        
        # Mock the actual API calls to avoid external dependencies
        with patch('requests.Session.post') as mock_post:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
            <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                <soap:Body>
                    <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                        <countryCode>DE</countryCode>
                        <vatNumber>143593636</vatNumber>
                        <requestDate>2025-01-01</requestDate>
                        <valid>true</valid>
                        <name>TEST</name>
                        <address>TEST</address>
                    </checkVatResponse>
                </soap:Body>
            </soap:Envelope>'''
            mock_post.return_value = mock_response
            
            results = vies_adapter.check_batch(vat_numbers, batch_delay=0.01)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Verify performance metrics
        assert len(results) == len(vat_numbers)
        for result in results:
            assert 'response_time_ms' in result
            assert isinstance(result['response_time_ms'], int)
        
        # Batch should complete reasonably quickly (allowing for delays)
        expected_max_time = len(vat_numbers) * 0.1 + 2  # batch_delay + overhead
        assert total_time < expected_max_time, f"Batch took too long: {total_time}s"


class TestVIESErrorHandling(TestVIESIntegrationKYB):
    """Test VIES error handling scenarios."""
    
    def test_invalid_vat_number_handling(self, vies_adapter):
        """Test handling of invalid VAT numbers."""
        invalid_vat_numbers = [
            "INVALID123",
            "DE12345",  # Too short
            "DE1234567890",  # Too long
            "US123456789",  # Non-EU country
            "",  # Empty
            "DE12345678A"  # Invalid format
        ]
        
        for invalid_vat in invalid_vat_numbers:
            result = vies_adapter.check_single(invalid_vat)
            assert result['status'] in ['validation_error', 'error'], f"Should fail for {invalid_vat}"
            assert result['valid'] is False
            assert 'error' in result
    
    @patch('requests.Session.post')
    def test_vies_service_unavailable(self, mock_post, vies_adapter, real_company_data):
        """Test handling when VIES service is unavailable."""
        # Mock service unavailable response
        mock_post.side_effect = Exception("Service unavailable")
        
        first_company = next(iter(real_company_data.values()))
        vat_number = first_company['vat_number']
        
        result = vies_adapter.check_single(vat_number)
        
        assert result['status'] == 'unavailable'
        assert result['valid'] is False
        assert 'error' in result
        assert result['source'] == 'VIES'
    
    @patch('requests.Session.post')
    def test_vies_timeout_handling(self, mock_post, vies_adapter, real_company_data):
        """Test handling of VIES API timeouts."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout("Request timeout")
        
        first_company = next(iter(real_company_data.values()))
        vat_number = first_company['vat_number']
        
        result = vies_adapter.check_single(vat_number, timeout=5)
        
        assert result['status'] == 'timeout'
        assert result['valid'] is False
        assert 'timeout' in result.get('error', '').lower()
    
    @patch('requests.Session.post')
    def test_vies_rate_limit_handling(self, mock_post, vies_adapter, mock_redis, real_company_data):
        """Test handling of VIES rate limits."""
        # Mock rate limit exceeded
        mock_redis.get.return_value = str(vies_adapter.RATE_LIMIT)  # At limit
        
        first_company = next(iter(real_company_data.values()))
        vat_number = first_company['vat_number']
        
        # Should not make API call due to rate limit
        result = vies_adapter.check_single(vat_number)
        
        # Should either return cached result or rate limit error
        assert result['status'] in ['rate_limited', 'cached', 'error']
        mock_post.assert_not_called()
    
    @patch('requests.Session.post')
    def test_vies_soap_fault_handling(self, mock_post, vies_adapter, real_company_data):
        """Test handling of VIES SOAP faults."""
        # Mock SOAP fault response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <soap:Fault>
                    <faultcode>soap:Server</faultcode>
                    <faultstring>INVALID_INPUT</faultstring>
                </soap:Fault>
            </soap:Body>
        </soap:Envelope>'''
        mock_post.return_value = mock_response
        
        first_company = next(iter(real_company_data.values()))
        vat_number = first_company['vat_number']
        
        result = vies_adapter.check_single(vat_number)
        
        assert result['status'] == 'soap_fault'
        assert result['valid'] is False
        assert 'INVALID_INPUT' in result.get('error', '')


class TestVIESKYBIntegration(TestVIESIntegrationKYB):
    """Test VIES integration with KYB monitoring workflow."""
    
    def test_counterparty_vat_validation_workflow(self, app, test_tenant, vies_adapter, real_company_data):
        """Test complete workflow from counterparty creation to VAT validation."""
        with app.app_context():
            # Create counterparty with real company data
            first_company = next(iter(real_company_data.values()))
            
            counterparty = Counterparty(
                tenant_id=test_tenant.id,
                name=first_company['name'],
                vat_number=first_company['vat_number'],
                country_code=first_company['country_code'],
                address=first_company.get('address', ''),
                status='active',
                monitoring_enabled=True
            )
            db.session.add(counterparty)
            db.session.commit()
            
            # Mock VIES validation
            with patch('requests.Session.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = f'''<?xml version="1.0" encoding="UTF-8"?>
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                            <countryCode>{first_company['country_code']}</countryCode>
                            <vatNumber>{first_company['vat_number'][2:]}</vatNumber>
                            <requestDate>2025-01-01</requestDate>
                            <valid>true</valid>
                            <name>{first_company['name']}</name>
                            <address>{first_company.get('address', 'TEST ADDRESS')}</address>
                        </checkVatResponse>
                    </soap:Body>
                </soap:Envelope>'''
                mock_post.return_value = mock_response
                
                # Perform VAT validation
                result = vies_adapter.check_single(counterparty.vat_number)
                
                # Create snapshot
                snapshot = CounterpartySnapshot(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    source='VIES',
                    check_type='vat',
                    data_hash='test_hash',
                    raw_data=result,
                    status=result['status'],
                    response_time_ms=result.get('response_time_ms', 0)
                )
                db.session.add(snapshot)
                db.session.commit()
            
            # Verify counterparty was created
            assert counterparty.id is not None
            assert counterparty.vat_number == first_company['vat_number']
            
            # Verify snapshot was created
            assert snapshot.id is not None
            assert snapshot.source == 'VIES'
            assert snapshot.check_type == 'vat'
            assert snapshot.counterparty_id == counterparty.id
    
    def test_vat_validation_alert_generation(self, app, test_tenant, vies_adapter, real_company_data):
        """Test alert generation for invalid VAT numbers."""
        with app.app_context():
            # Create counterparty with potentially invalid VAT
            counterparty = Counterparty(
                tenant_id=test_tenant.id,
                name="Test Invalid Company",
                vat_number="DE999999999",  # Likely invalid
                country_code="DE",
                status='active',
                monitoring_enabled=True
            )
            db.session.add(counterparty)
            db.session.commit()
            
            # Mock invalid VIES response
            with patch('requests.Session.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                            <countryCode>DE</countryCode>
                            <vatNumber>999999999</vatNumber>
                            <requestDate>2025-01-01</requestDate>
                            <valid>false</valid>
                            <name>---</name>
                            <address>---</address>
                        </checkVatResponse>
                    </soap:Body>
                </soap:Envelope>'''
                mock_post.return_value = mock_response
                
                # Perform VAT validation
                result = vies_adapter.check_single(counterparty.vat_number)
                
                # Create snapshot
                snapshot = CounterpartySnapshot(
                    tenant_id=test_tenant.id,
                    counterparty_id=counterparty.id,
                    source='VIES',
                    check_type='vat',
                    data_hash='test_hash',
                    raw_data=result,
                    status=result['status'],
                    response_time_ms=result.get('response_time_ms', 0)
                )
                db.session.add(snapshot)
                
                # Create alert for invalid VAT
                if not result.get('valid', False):
                    alert = KYBAlert(
                        tenant_id=test_tenant.id,
                        counterparty_id=counterparty.id,
                        alert_type='validation_failure',
                        severity='medium',
                        title='Invalid VAT Number',
                        message=f'VAT number {counterparty.vat_number} is invalid according to VIES',
                        source='VIES',
                        status='open'
                    )
                    db.session.add(alert)
                
                db.session.commit()
            
            # Verify alert was created
            alerts = KYBAlert.query.filter_by(counterparty_id=counterparty.id).all()
            assert len(alerts) > 0
            alert = alerts[0]
            assert alert.alert_type == 'validation_failure'
            assert alert.severity == 'medium'
            assert 'invalid' in alert.message.lower()
    
    def test_batch_counterparty_monitoring(self, app, test_tenant, vies_adapter, real_company_data):
        """Test batch monitoring of multiple counterparties."""
        with app.app_context():
            # Create multiple counterparties from real data
            counterparties = []
            for i, (key, company) in enumerate(list(real_company_data.items())[:3]):
                counterparty = Counterparty(
                    tenant_id=test_tenant.id,
                    name=company['name'],
                    vat_number=company['vat_number'],
                    country_code=company['country_code'],
                    address=company.get('address', ''),
                    status='active',
                    monitoring_enabled=True
                )
                db.session.add(counterparty)
                counterparties.append(counterparty)
            
            db.session.commit()
            
            # Collect VAT numbers for batch processing
            vat_numbers = [cp.vat_number for cp in counterparties]
            
            # Mock batch VIES validation
            with patch('requests.Session.post') as mock_post:
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = '''<?xml version="1.0" encoding="UTF-8"?>
                <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
                    <soap:Body>
                        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
                            <countryCode>DE</countryCode>
                            <vatNumber>143593636</vatNumber>
                            <requestDate>2025-01-01</requestDate>
                            <valid>true</valid>
                            <name>TEST COMPANY</name>
                            <address>TEST ADDRESS</address>
                        </checkVatResponse>
                    </soap:Body>
                </soap:Envelope>'''
                mock_post.return_value = mock_response
                
                # Perform batch validation
                results = vies_adapter.check_batch(vat_numbers, batch_delay=0.01)
                
                # Create snapshots for all results
                for i, result in enumerate(results):
                    snapshot = CounterpartySnapshot(
                        tenant_id=test_tenant.id,
                        counterparty_id=counterparties[i].id,
                        source='VIES',
                        check_type='vat',
                        data_hash=f'test_hash_{i}',
                        raw_data=result,
                        status=result['status'],
                        response_time_ms=result.get('response_time_ms', 0)
                    )
                    db.session.add(snapshot)
                
                db.session.commit()
            
            # Verify all snapshots were created
            snapshots = CounterpartySnapshot.query.filter_by(tenant_id=test_tenant.id).all()
            assert len(snapshots) == len(counterparties)
            
            for snapshot in snapshots:
                assert snapshot.source == 'VIES'
                assert snapshot.check_type == 'vat'
                assert snapshot.counterparty_id in [cp.id for cp in counterparties]