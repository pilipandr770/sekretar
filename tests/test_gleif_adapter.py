"""Tests for GLEIF LEI validation adapter."""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests

from app.services.kyb_adapters.gleif import GLEIFAdapter
from app.services.kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded


class TestGLEIFAdapter:
    """Test cases for GLEIF adapter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.adapter = GLEIFAdapter()
        self.valid_lei = "213800WAVVOPS85N2205"  # Example LEI
        self.invalid_lei = "INVALID123456789012"
        
        # Mock GLEIF API response for valid LEI
        self.valid_response = {
            "data": {
                "id": self.valid_lei,
                "type": "lei-records",
                "attributes": {
                    "lei": self.valid_lei,
                    "entity": {
                        "legalName": {
                            "name": "Test Company Ltd"
                        },
                        "legalForm": {
                            "id": "XTIQ"
                        },
                        "status": "ACTIVE",
                        "legalAddress": {
                            "addressLines_1": "123 Test Street",
                            "city": "London",
                            "country": "GB",
                            "postalCode": "SW1A 1AA"
                        },
                        "headquartersAddress": {
                            "addressLines_1": "123 Test Street",
                            "city": "London", 
                            "country": "GB",
                            "postalCode": "SW1A 1AA"
                        }
                    },
                    "registration": {
                        "registrationAuthority": {
                            "id": "RA000665",
                            "other": "Companies House"
                        }
                    }
                }
            }
        }
    
    def test_validate_lei_format_valid(self):
        """Test LEI format validation with valid LEI."""
        result = self.adapter.validate_lei_format(self.valid_lei)
        
        assert result['valid'] is True
        assert result['lei_code'] == self.valid_lei
        assert 'message' in result
    
    def test_validate_lei_format_invalid_length(self):
        """Test LEI format validation with invalid length."""
        result = self.adapter.validate_lei_format("123456789")
        
        assert result['valid'] is False
        assert 'error' in result
        assert 'LEI must be 20 alphanumeric characters' in result['error']
    
    def test_validate_lei_format_invalid_characters(self):
        """Test LEI format validation with invalid characters."""
        result = self.adapter.validate_lei_format("12345678901234567890")  # Contains invalid chars
        
        assert result['valid'] is False
        assert 'error' in result
    
    def test_validate_lei_format_empty(self):
        """Test LEI format validation with empty string."""
        result = self.adapter.validate_lei_format("")
        
        assert result['valid'] is False
        assert 'error' in result
        assert 'LEI code cannot be empty' in result['error']
    
    def test_validate_lei_format_with_spaces(self):
        """Test LEI format validation with spaces and hyphens."""
        lei_with_spaces = "2138-00WA-VVOP-S85N-2205"
        result = self.adapter.validate_lei_format(lei_with_spaces)
        
        assert result['valid'] is True
        assert result['lei_code'] == self.valid_lei
    
    @patch('requests.Session.get')
    def test_check_single_valid_lei(self, mock_get):
        """Test checking a valid LEI code."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.valid_response
        mock_get.return_value = mock_response
        
        result = self.adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'valid'
        assert result['valid'] is True
        assert result['lei_code'] == self.valid_lei
        assert result['legal_name'] == 'Test Company Ltd'
        assert result['entity_status'] == 'ACTIVE'
        assert 'legal_address' in result
        assert 'headquarters_address' in result
        assert result['cached'] is False
        assert 'response_time_ms' in result
    
    @patch('requests.Session.get')
    def test_check_single_not_found(self, mock_get):
        """Test checking a LEI code that doesn't exist."""
        # Mock 404 response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'not_found'
        assert result['valid'] is False
        assert 'LEI code not found' in result['error']
        assert result['lei_code'] == self.valid_lei
    
    @patch('requests.Session.get')
    def test_check_single_api_error(self, mock_get):
        """Test handling API errors."""
        # Mock 500 error response
        mock_response = Mock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response
        
        result = self.adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'unavailable'
        assert 'GLEIF API server error' in result['error']
    
    @patch('requests.Session.get')
    def test_check_single_timeout(self, mock_get):
        """Test handling request timeout."""
        # Mock timeout exception
        mock_get.side_effect = requests.exceptions.Timeout("Request timeout")
        
        result = self.adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'unavailable'
        assert 'timeout' in result['error'].lower()
    
    @patch('requests.Session.get')
    def test_check_single_connection_error(self, mock_get):
        """Test handling connection errors."""
        # Mock connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection failed")
        
        result = self.adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'unavailable'
        assert 'Cannot connect to GLEIF API' in result['error']
    
    def test_check_single_invalid_format(self):
        """Test checking LEI with invalid format."""
        result = self.adapter.check_single("INVALID")
        
        assert result['status'] == 'validation_error'
        assert 'LEI must be 20 alphanumeric characters' in result['error']
    
    @patch('requests.Session.get')
    def test_check_single_with_cache(self, mock_get):
        """Test caching functionality."""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None  # No cache initially
        mock_redis.setex = Mock()
        
        adapter = GLEIFAdapter(redis_client=mock_redis)
        
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.valid_response
        mock_get.return_value = mock_response
        
        result = adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'valid'
        assert result['cached'] is False
        
        # Verify cache was written
        mock_redis.setex.assert_called_once()
    
    @patch('requests.Session.get')
    def test_check_single_cache_hit(self, mock_get):
        """Test cache hit scenario."""
        # Mock cached result
        cached_result = {
            'status': 'valid',
            'valid': True,
            'lei_code': self.valid_lei,
            'legal_name': 'Cached Company'
        }
        
        mock_redis = Mock()
        mock_redis.get.return_value = json.dumps(cached_result)
        
        adapter = GLEIFAdapter(redis_client=mock_redis)
        
        result = adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'valid'
        assert result['cached'] is True
        assert result['legal_name'] == 'Cached Company'
        
        # Verify API was not called
        mock_get.assert_not_called()
    
    @patch('requests.Session.get')
    def test_check_batch(self, mock_get):
        """Test batch checking functionality."""
        lei_codes = [self.valid_lei, "213800WAVVOPS85N2206"]
        
        # Mock successful API responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.valid_response
        mock_get.return_value = mock_response
        
        results = self.adapter.check_batch(lei_codes)
        
        assert len(results) == 2
        assert all(r['status'] in ['valid', 'not_found', 'error'] for r in results)
        
        # Verify API was called for each LEI
        assert mock_get.call_count == 2
    
    @patch('requests.Session.get')
    def test_check_batch_with_errors(self, mock_get):
        """Test batch checking with some errors."""
        lei_codes = [self.valid_lei, "INVALID", self.valid_lei]
        
        # Mock successful API response for valid LEIs
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.valid_response
        mock_get.return_value = mock_response
        
        results = self.adapter.check_batch(lei_codes)
        
        assert len(results) == 3
        assert results[0]['status'] == 'valid'  # Valid LEI
        assert results[1]['status'] == 'validation_error'  # Invalid format
        assert results[2]['status'] == 'valid'  # Valid LEI
    
    @patch('requests.Session.get')
    def test_search_by_name(self, mock_get):
        """Test searching LEI by entity name."""
        # Mock search response
        search_response = {
            "data": [
                {
                    "id": self.valid_lei,
                    "type": "lei-records",
                    "attributes": self.valid_response["data"]["attributes"]
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = search_response
        mock_get.return_value = mock_response
        
        results = self.adapter.search_by_name("Test Company")
        
        assert len(results) == 1
        assert results[0]['lei_code'] == self.valid_lei
        assert results[0]['legal_name'] == 'Test Company Ltd'
    
    @patch('requests.Session.get')
    def test_search_by_name_with_country(self, mock_get):
        """Test searching LEI by entity name with country filter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": []}
        mock_get.return_value = mock_response
        
        results = self.adapter.search_by_name("Test Company", country_code="GB")
        
        assert len(results) == 0
        
        # Verify country filter was applied
        call_args = mock_get.call_args
        assert 'filter[entity.legalAddress.country]' in call_args[1]['params']
        assert call_args[1]['params']['filter[entity.legalAddress.country]'] == 'GB'
    
    @patch('requests.Session.get')
    def test_get_lei_relationships(self, mock_get):
        """Test getting LEI relationships."""
        relationships_response = {
            "data": [
                {
                    "type": "relationship-records",
                    "attributes": {
                        "relationship": {
                            "relationshipType": "IS_DIRECTLY_CONSOLIDATED_BY"
                        }
                    }
                }
            ]
        }
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = relationships_response
        mock_get.return_value = mock_response
        
        result = self.adapter.get_lei_relationships(self.valid_lei)
        
        assert result['status'] == 'success'
        assert result['lei_code'] == self.valid_lei
        assert 'relationships' in result
    
    @patch('requests.Session.get')
    def test_get_lei_relationships_not_found(self, mock_get):
        """Test getting relationships for non-existent LEI."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        result = self.adapter.get_lei_relationships(self.valid_lei)
        
        assert result['status'] == 'not_found'
        assert 'No relationships found' in result['error']
    
    def test_get_lei_relationships_invalid_format(self):
        """Test getting relationships with invalid LEI format."""
        result = self.adapter.get_lei_relationships("INVALID")
        
        assert result['status'] == 'validation_error'
        assert 'LEI must be 20 alphanumeric characters' in result['error']
    
    def test_lei_checksum_validation(self):
        """Test LEI checksum validation."""
        # Valid LEI with correct checksum
        valid_lei = "213800WAVVOPS85N2205"
        assert self.adapter._validate_lei_checksum(valid_lei) is True
        
        # Invalid LEI with wrong checksum
        invalid_lei = "213800WAVVOPS85N2200"  # Wrong check digits
        assert self.adapter._validate_lei_checksum(invalid_lei) is False
    
    def test_format_address(self):
        """Test address formatting."""
        address_data = {
            "addressLines_1": "123 Test Street",
            "addressLines_2": "Suite 100",
            "city": "London",
            "region": "England",
            "postalCode": "SW1A 1AA",
            "country": "GB"
        }
        
        formatted = self.adapter._format_address(address_data)
        expected = "123 Test Street, Suite 100, London, England, SW1A 1AA, GB"
        
        assert formatted == expected
    
    def test_format_address_empty(self):
        """Test address formatting with empty data."""
        assert self.adapter._format_address({}) is None
        assert self.adapter._format_address(None) is None
    
    def test_format_address_partial(self):
        """Test address formatting with partial data."""
        address_data = {
            "city": "London",
            "country": "GB"
        }
        
        formatted = self.adapter._format_address(address_data)
        assert formatted == "London, GB"
    
    @patch('requests.Session.get')
    def test_rate_limiting(self, mock_get):
        """Test rate limiting functionality."""
        # Mock Redis client with rate limit exceeded
        mock_redis = Mock()
        mock_redis.get.return_value = "100"  # Current count at limit
        
        adapter = GLEIFAdapter(redis_client=mock_redis)
        adapter.rate_limit = 100  # Set rate limit
        
        result = adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'rate_limited'
        assert 'Rate limit exceeded' in result['error']
        
        # Verify API was not called
        mock_get.assert_not_called()
    
    @patch('requests.Session.get')
    def test_inactive_lei_warning(self, mock_get):
        """Test handling of inactive LEI codes."""
        # Mock response with inactive LEI
        inactive_response = self.valid_response.copy()
        inactive_response["data"]["attributes"]["entity"]["status"] = "INACTIVE"
        
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = inactive_response
        mock_get.return_value = mock_response
        
        result = self.adapter.check_single(self.valid_lei)
        
        assert result['status'] == 'valid'  # Still valid but inactive
        assert result['entity_status'] == 'INACTIVE'
        assert 'warning' in result
        assert 'inactive but still valid' in result['warning']
    
    @patch('requests.Session.get')
    def test_force_refresh(self, mock_get):
        """Test force refresh bypasses cache."""
        # Mock cached result
        cached_result = {
            'status': 'valid',
            'legal_name': 'Cached Company'
        }
        
        mock_redis = Mock()
        mock_redis.get.return_value = json.dumps(cached_result)
        
        adapter = GLEIFAdapter(redis_client=mock_redis)
        
        # Mock fresh API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = self.valid_response
        mock_get.return_value = mock_response
        
        result = adapter.check_single(self.valid_lei, force_refresh=True)
        
        assert result['status'] == 'valid'
        assert result['legal_name'] == 'Test Company Ltd'  # Fresh data, not cached
        assert result['cached'] is False
        
        # Verify API was called despite cache
        mock_get.assert_called_once()


class TestGLEIFAdapterIntegration:
    """Integration tests for GLEIF adapter (require network access)."""
    
    @pytest.mark.integration
    def test_real_lei_check(self):
        """Test with a real LEI code (requires internet)."""
        adapter = GLEIFAdapter()
        
        # Use a known valid LEI (Apple Inc.)
        lei_code = "HWUPKR0MPOU8FGXBT394"
        
        result = adapter.check_single(lei_code)
        
        # Should get a valid response (or at least not a validation error)
        assert result['status'] in ['valid', 'not_found', 'unavailable']
        assert result['identifier'] == lei_code
        
        if result['status'] == 'valid':
            assert 'legal_name' in result
            assert 'entity_status' in result
    
    @pytest.mark.integration
    def test_real_lei_search(self):
        """Test searching for a real company (requires internet)."""
        adapter = GLEIFAdapter()
        
        results = adapter.search_by_name("Apple Inc", limit=5)
        
        # Should get some results or empty list (not an error)
        assert isinstance(results, list)
        
        if results:
            assert all('lei_code' in r for r in results)
            assert all('legal_name' in r for r in results)