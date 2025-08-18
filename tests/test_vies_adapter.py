"""Tests for VIES adapter."""
import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from app.services.kyb_adapters.vies import VIESAdapter
from app.services.kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded


@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = Mock()
    redis_mock.get.return_value = None
    redis_mock.setex.return_value = True
    redis_mock.incr.return_value = 1
    redis_mock.keys.return_value = []
    redis_mock.delete.return_value = 0
    return redis_mock


@pytest.fixture
def vies_adapter(mock_redis):
    """Create VIES adapter instance with mocked Redis."""
    return VIESAdapter(redis_client=mock_redis)


@pytest.fixture
def mock_successful_response():
    """Mock successful VIES response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
            <countryCode>DE</countryCode>
            <vatNumber>123456789</vatNumber>
            <requestDate>2024-01-15</requestDate>
            <valid>true</valid>
            <name>Test Company GmbH</name>
            <address>Test Street 123, 12345 Test City</address>
        </checkVatResponse>
    </soap:Body>
</soap:Envelope>"""


@pytest.fixture
def mock_invalid_response():
    """Mock invalid VAT response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <checkVatResponse xmlns="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
            <countryCode>DE</countryCode>
            <vatNumber>999999999</vatNumber>
            <requestDate>2024-01-15</requestDate>
            <valid>false</valid>
        </checkVatResponse>
    </soap:Body>
</soap:Envelope>"""


@pytest.fixture
def mock_fault_response():
    """Mock SOAP fault response."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <soap:Fault>
            <faultcode>soap:Server</faultcode>
            <faultstring>INVALID_INPUT</faultstring>
        </soap:Fault>
    </soap:Body>
</soap:Envelope>"""


class TestVATNumberValidation:
    """Test VAT number validation and parsing."""
    
    def test_parse_vat_number_with_country_prefix(self, vies_adapter):
        """Test parsing VAT number with country prefix."""
        country, vat = vies_adapter._parse_vat_number("DE123456789")
        assert country == "DE"
        assert vat == "123456789"
    
    def test_parse_vat_number_with_separate_country(self, vies_adapter):
        """Test parsing VAT number with separate country code."""
        country, vat = vies_adapter._parse_vat_number("123456789", "DE")
        assert country == "DE"
        assert vat == "123456789"
    
    def test_parse_vat_number_with_spaces_and_dashes(self, vies_adapter):
        """Test parsing VAT number with formatting characters."""
        country, vat = vies_adapter._parse_vat_number("DE 123-456-789")
        assert country == "DE"
        assert vat == "123456789"
    
    def test_parse_vat_number_empty(self, vies_adapter):
        """Test parsing empty VAT number."""
        with pytest.raises(ValidationError, match="VAT number cannot be empty"):
            vies_adapter._parse_vat_number("")
    
    def test_parse_vat_number_no_country(self, vies_adapter):
        """Test parsing VAT number without country code."""
        with pytest.raises(ValidationError, match="Country code must be provided"):
            vies_adapter._parse_vat_number("123456789")
    
    def test_parse_vat_number_invalid_country(self, vies_adapter):
        """Test parsing VAT number with invalid country code."""
        with pytest.raises(ValidationError, match="not supported by VIES"):
            vies_adapter._parse_vat_number("123456789", "US")
    
    def test_validate_vat_format_valid(self, vies_adapter):
        """Test VAT format validation for valid number."""
        result = vies_adapter.validate_vat_format("DE123456789")
        assert result['valid'] is True
        assert result['country_code'] == 'DE'
        assert result['vat_number'] == '123456789'
    
    def test_validate_vat_format_invalid(self, vies_adapter):
        """Test VAT format validation for invalid number."""
        result = vies_adapter.validate_vat_format("INVALID")
        assert result['valid'] is False
        assert 'error' in result


class TestSingleVATCheck:
    """Test single VAT number checking."""
    
    @patch('requests.Session.post')
    def test_check_single_valid_vat(self, mock_post, vies_adapter, mock_successful_response):
        """Test checking valid VAT number."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_successful_response
        mock_post.return_value = mock_response
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['status'] == 'valid'
        assert result['valid'] is True
        assert result['country_code'] == 'DE'
        assert result['vat_number'] == '123456789'
        assert result['company_name'] == 'Test Company GmbH'
        assert 'response_time_ms' in result
        assert 'checked_at' in result
    
    @patch('requests.Session.post')
    def test_check_single_invalid_vat(self, mock_post, vies_adapter, mock_invalid_response):
        """Test checking invalid VAT number."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_invalid_response
        mock_post.return_value = mock_response
        
        result = vies_adapter.check_single("DE999999999")
        
        assert result['status'] == 'invalid'
        assert result['valid'] is False
        assert result['country_code'] == 'DE'
        assert result['vat_number'] == '999999999'
    
    @patch('requests.Session.post')
    def test_check_single_soap_fault(self, mock_post, vies_adapter, mock_fault_response):
        """Test handling SOAP fault response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_fault_response
        mock_post.return_value = mock_response
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['status'] == 'invalid'
        assert result['valid'] is False
        assert 'Invalid VAT number format' in result['error']
    
    @patch('requests.Session.post')
    def test_check_single_http_error(self, mock_post, vies_adapter):
        """Test handling HTTP error response."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['status'] == 'unavailable'
        assert 'server error' in result['error']
    
    @patch('requests.Session.post')
    def test_check_single_timeout(self, mock_post, vies_adapter):
        """Test handling request timeout."""
        import requests
        mock_post.side_effect = requests.exceptions.Timeout()
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['status'] == 'unavailable'
        assert 'timeout' in result['error']
    
    @patch('requests.Session.post')
    def test_check_single_connection_error(self, mock_post, vies_adapter):
        """Test handling connection error."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError()
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['status'] == 'unavailable'
        assert 'network issue' in result['error']


class TestCaching:
    """Test caching functionality."""
    
    def test_cache_hit(self, vies_adapter, mock_redis):
        """Test cache hit scenario."""
        cached_result = {
            'status': 'valid',
            'valid': True,
            'country_code': 'DE',
            'vat_number': '123456789'
        }
        mock_redis.get.return_value = json.dumps(cached_result)
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['cached'] is True
        assert result['status'] == 'valid'
        mock_redis.get.assert_called_once()
    
    @patch('requests.Session.post')
    def test_cache_miss_and_store(self, mock_post, vies_adapter, mock_redis, mock_successful_response):
        """Test cache miss and subsequent storage."""
        mock_redis.get.return_value = None  # Cache miss
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_successful_response
        mock_post.return_value = mock_response
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['cached'] is False
        assert result['status'] == 'valid'
        # Should be called twice: once for rate limiting, once for caching
        assert mock_redis.setex.call_count == 2
    
    def test_force_refresh_skips_cache(self, vies_adapter, mock_redis):
        """Test force refresh skips cache."""
        cached_result = {
            'status': 'valid',
            'valid': True,
            'country_code': 'DE',
            'vat_number': '123456789'
        }
        # Setup mock to return None for rate limit check, then cached result for cache check
        mock_redis.get.side_effect = [None, json.dumps(cached_result)]
        
        with patch('requests.Session.post') as mock_post:
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
            
            result = vies_adapter.check_single("DE123456789", force_refresh=True)
            
            assert result['cached'] is False
            mock_post.assert_called_once()


class TestRateLimiting:
    """Test rate limiting functionality."""
    
    def test_rate_limit_not_exceeded(self, vies_adapter, mock_redis):
        """Test rate limit check when limit not exceeded."""
        mock_redis.get.return_value = "5"  # Current count below limit
        
        result = vies_adapter._check_rate_limit()
        
        assert result is True
        mock_redis.incr.assert_called_once()
    
    def test_rate_limit_exceeded(self, vies_adapter, mock_redis):
        """Test rate limit check when limit exceeded."""
        mock_redis.get.return_value = str(vies_adapter.RATE_LIMIT)  # At limit
        
        result = vies_adapter._check_rate_limit()
        
        assert result is False
        mock_redis.incr.assert_not_called()
    
    def test_rate_limit_first_request(self, vies_adapter, mock_redis):
        """Test rate limit check for first request in window."""
        mock_redis.get.return_value = None  # No previous requests
        
        result = vies_adapter._check_rate_limit()
        
        assert result is True
        mock_redis.setex.assert_called_once()


class TestBatchProcessing:
    """Test batch processing functionality."""
    
    @patch('requests.Session.post')
    def test_batch_check_success(self, mock_post, vies_adapter, mock_successful_response):
        """Test successful batch processing."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_successful_response
        mock_post.return_value = mock_response
        
        vat_numbers = ["DE123456789", "FR12345678901"]
        results = vies_adapter.check_batch(vat_numbers, batch_delay=0)
        
        assert len(results) == 2
        assert all(r['status'] in ['valid', 'invalid', 'error'] for r in results)
    
    def test_batch_check_empty_list(self, vies_adapter):
        """Test batch processing with empty list."""
        results = vies_adapter.check_batch([])
        assert results == []
    
    @patch('requests.Session.post')
    def test_batch_check_with_errors(self, mock_post, vies_adapter):
        """Test batch processing with some errors."""
        def side_effect(*args, **kwargs):
            import requests
            raise requests.exceptions.Timeout()
        
        mock_post.side_effect = side_effect
        
        vat_numbers = ["DE123456789", "INVALID"]
        results = vies_adapter.check_batch(vat_numbers, batch_delay=0)
        
        assert len(results) == 2
        assert all(r['status'] == 'unavailable' or r['status'] == 'validation_error' for r in results)
    
    def test_batch_check_optimized_with_cache(self, vies_adapter, mock_redis):
        """Test optimized batch processing with cached results."""
        # Setup cache hit for first item
        cached_result = {
            'status': 'valid',
            'valid': True,
            'country_code': 'DE',
            'vat_number': '123456789'
        }
        mock_redis.get.side_effect = [json.dumps(cached_result), None]
        
        vat_data = [
            {'vat_number': 'DE123456789'},
            {'vat_number': 'FR12345678901'}
        ]
        
        with patch.object(vies_adapter, 'check_batch') as mock_batch:
            mock_batch.return_value = [{'status': 'valid', 'identifier': 'FR12345678901'}]
            
            results = vies_adapter.check_batch_optimized(vat_data)
            
            assert len(results) == 2
            assert results[0]['cached'] is True  # First result from cache
            mock_batch.assert_called_once()  # Only uncached items processed


class TestUtilityMethods:
    """Test utility methods."""
    
    def test_get_supported_countries(self, vies_adapter):
        """Test getting supported countries."""
        countries = vies_adapter.get_supported_countries()
        
        assert len(countries) > 0
        assert all('code' in country and 'name' in country for country in countries)
        assert any(country['code'] == 'DE' for country in countries)
    
    def test_get_cache_stats(self, vies_adapter, mock_redis):
        """Test getting cache statistics."""
        mock_redis.keys.return_value = ['key1', 'key2', 'key3']
        
        stats = vies_adapter.get_cache_stats()
        
        assert 'cache_stats' in stats
        assert 'total_cached_items' in stats['cache_stats']
    
    def test_clear_cache(self, vies_adapter, mock_redis):
        """Test clearing cache."""
        mock_redis.keys.return_value = ['key1', 'key2']
        mock_redis.delete.return_value = 2
        
        result = vies_adapter.clear_cache()
        
        assert result['success'] is True
        assert result['keys_deleted'] == 2
        mock_redis.delete.assert_called_once()
    
    @patch('requests.Session.post')
    def test_health_check_healthy(self, mock_post, vies_adapter, mock_successful_response):
        """Test health check when service is healthy."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_successful_response
        mock_post.return_value = mock_response
        
        result = vies_adapter.health_check()
        
        assert result['status'] == 'healthy'
        assert 'response_time_ms' in result
    
    @patch('requests.Session.post')
    def test_health_check_unhealthy(self, mock_post, vies_adapter):
        """Test health check when service is unhealthy."""
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = vies_adapter.health_check()
        
        # Connection errors result in 'degraded' status, not 'unhealthy'
        # 'unhealthy' is only for exceptions in the health check itself
        assert result['status'] == 'degraded'
        assert 'error' in result


class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_validation_error_handling(self, vies_adapter):
        """Test validation error handling."""
        result = vies_adapter.check_single("")
        
        assert result['status'] == 'validation_error'
        assert 'error' in result
    
    def test_rate_limit_with_stale_cache(self, vies_adapter, mock_redis):
        """Test rate limit handling with stale cache fallback."""
        # Setup rate limit exceeded and stale cache available
        cached_result = {'status': 'valid', 'valid': True}
        
        # Mock the get calls in order:
        # 1. First call for cache check (before rate limit) - return None (cache miss)
        # 2. Second call for rate limit check - return at limit
        # 3. Third call for stale cache fallback - return cached result
        mock_redis.get.side_effect = [
            None,  # Initial cache check
            str(vies_adapter.RATE_LIMIT),  # Rate limit check - at limit
            json.dumps(cached_result)  # Stale cache available
        ]
        
        result = vies_adapter.check_single("DE123456789")
        
        assert result['cached'] is True
        assert result['stale'] is True
        assert 'Rate limited' in result['warning']
    
    def test_concurrent_batch_processing(self, vies_adapter):
        """Test concurrent batch processing doesn't break."""
        vat_numbers = ["DE123456789", "FR12345678901", "IT12345678901"]
        
        with patch.object(vies_adapter, '_safe_check_single') as mock_safe_check:
            mock_safe_check.return_value = {'status': 'valid', 'identifier': 'test'}
            
            results = vies_adapter.check_batch(vat_numbers, max_workers=2, batch_delay=0)
            
            assert len(results) == 3
            assert mock_safe_check.call_count == 3


if __name__ == '__main__':
    pytest.main([__file__])