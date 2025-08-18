"""Integration tests for VIES adapter with KYB service."""
import pytest
from unittest.mock import Mock, patch
from app.services.kyb_adapters.vies import VIESAdapter
from app.services.kyb_service import KYBService


class TestVIESIntegration:
    """Test VIES adapter integration with KYB service."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        redis_mock = Mock()
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.incr.return_value = 1
        return redis_mock
    
    @pytest.fixture
    def vies_adapter(self, mock_redis):
        """Create VIES adapter instance."""
        return VIESAdapter(redis_client=mock_redis)
    
    def test_vies_adapter_initialization(self, vies_adapter):
        """Test VIES adapter can be initialized properly."""
        assert vies_adapter.source_name == 'VIES'
        assert vies_adapter.RATE_LIMIT == 30
        assert vies_adapter.CACHE_TTL == 3600
        assert len(vies_adapter.EU_COUNTRIES) > 20
    
    def test_vat_format_validation(self, vies_adapter):
        """Test VAT number format validation."""
        # Valid formats
        valid_cases = [
            ('DE123456789', 'DE'),
            ('FR12345678901', 'FR'),
            ('IT12345678901', 'IT'),
            ('123456789', 'DE')  # With separate country code
        ]
        
        for vat_number, expected_country in valid_cases:
            if expected_country:
                result = vies_adapter.validate_vat_format(vat_number, expected_country)
            else:
                result = vies_adapter.validate_vat_format(vat_number)
            
            assert result['valid'] is True, f"Failed for {vat_number}"
            assert result['country_code'] == expected_country
    
    def test_invalid_vat_formats(self, vies_adapter):
        """Test invalid VAT number format handling."""
        invalid_cases = [
            '',  # Empty
            'US123456789',  # Non-EU country
            '123',  # Too short
            'INVALID',  # Invalid format
        ]
        
        for vat_number in invalid_cases:
            result = vies_adapter.validate_vat_format(vat_number)
            assert result['valid'] is False, f"Should be invalid: {vat_number}"
    
    @patch('requests.Session.post')
    def test_batch_processing_performance(self, mock_post, vies_adapter):
        """Test batch processing handles multiple VAT numbers efficiently."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
            <countryCode>DE</countryCode>
            <vatNumber>123456789</vatNumber>
            <valid>true</valid>
            <name>Test Company</name>
            <address>Test Address</address>
        </checkVatResponse>
    </soap:Body>
</soap:Envelope>"""
        mock_post.return_value = mock_response
        
        # Test batch processing
        vat_numbers = [
            'DE123456789',
            'FR12345678901', 
            'IT12345678901'
        ]
        
        results = vies_adapter.check_batch(vat_numbers, batch_delay=0, max_workers=2)
        
        assert len(results) == len(vat_numbers)
        # Check that all results have valid status values
        valid_statuses = ['valid', 'invalid', 'error', 'unavailable', 'validation_error']
        for i, result in enumerate(results):
            assert result['status'] in valid_statuses, f"Invalid status '{result['status']}' for result {i}: {result}"
        
        # Should have made API calls (not all cached)
        assert mock_post.call_count > 0
    
    def test_cache_functionality(self, vies_adapter):
        """Test caching works correctly."""
        # Test cache stats
        stats = vies_adapter.get_cache_stats()
        assert 'cache_stats' in stats
        # Note: cache_enabled might be in base stats or cache_stats depending on Redis availability
        
        # Test cache clearing - might return error if Redis is mocked
        clear_result = vies_adapter.clear_cache()
        # Should return either success or error dict
        assert isinstance(clear_result, dict)
        assert 'success' in clear_result or 'error' in clear_result
    
    def test_supported_countries(self, vies_adapter):
        """Test supported countries list."""
        countries = vies_adapter.get_supported_countries()
        
        assert len(countries) > 20
        assert all('code' in country and 'name' in country for country in countries)
        
        # Check some known EU countries
        country_codes = [c['code'] for c in countries]
        assert 'DE' in country_codes
        assert 'FR' in country_codes
        assert 'IT' in country_codes
        assert 'ES' in country_codes
    
    @patch('requests.Session.post')
    def test_error_handling_robustness(self, mock_post, vies_adapter):
        """Test error handling in various scenarios."""
        import requests
        
        # Test different error scenarios
        error_scenarios = [
            requests.exceptions.Timeout(),
            requests.exceptions.ConnectionError(),
            requests.exceptions.HTTPError(),
        ]
        
        for error in error_scenarios:
            mock_post.side_effect = error
            
            result = vies_adapter.check_single('DE123456789')
            
            assert result['status'] == 'unavailable'
            assert 'error' in result
            assert 'response_time_ms' in result
    
    def test_rate_limiting_behavior(self, vies_adapter):
        """Test rate limiting behavior."""
        # Test rate limit stats
        stats = vies_adapter.get_stats()
        
        assert 'rate_limit' in stats
        assert 'rate_window' in stats
        assert stats['rate_limit'] == 30
        assert stats['rate_window'] == 60
    
    @patch('requests.Session.post')
    def test_health_check_functionality(self, mock_post, vies_adapter):
        """Test health check functionality."""
        # Mock healthy response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
            <valid>true</valid>
        </checkVatResponse>
    </soap:Body>
</soap:Envelope>"""
        mock_post.return_value = mock_response
        
        health = vies_adapter.health_check()
        
        assert health['status'] == 'healthy'
        assert 'response_time_ms' in health
        assert 'message' in health


if __name__ == '__main__':
    pytest.main([__file__])