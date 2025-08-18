"""GLEIF (Global Legal Entity Identifier Foundation) API adapter."""
import time
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from flask import current_app
import structlog
from concurrent.futures import ThreadPoolExecutor, as_completed

from .base import BaseKYBAdapter, ValidationError, DataSourceUnavailable, RateLimitExceeded

logger = structlog.get_logger()


class GLEIFAdapter(BaseKYBAdapter):
    """Adapter for GLEIF LEI validation API."""
    
    # Configuration
    RATE_LIMIT = 100  # GLEIF allows more requests than VIES
    RATE_WINDOW = 60  # per minute
    CACHE_TTL = 7200  # 2 hours cache (LEI data changes less frequently)
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds
    
    # GLEIF API endpoints
    BASE_URL = "https://api.gleif.org/api/v1"
    LEI_RECORDS_ENDPOINT = "/lei-records"
    
    # LEI format validation pattern (20 alphanumeric characters)
    LEI_PATTERN = r'^[A-Z0-9]{20}$'
    
    def __init__(self, redis_client=None):
        """Initialize GLEIF adapter."""
        super().__init__(redis_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Secretary-KYB/1.0',
            'Accept': 'application/vnd.api+json',
            'Content-Type': 'application/vnd.api+json'
        })
        
        # Get API URL from config (handle case when no Flask app context)
        try:
            self.base_url = current_app.config.get('GLEIF_API_URL', self.BASE_URL)
        except RuntimeError:
            # No Flask app context, use default
            self.base_url = self.BASE_URL
            
        if not self.base_url.endswith('/api/v1'):
            if self.base_url.endswith('/'):
                self.base_url = self.base_url.rstrip('/') + '/api/v1'
            else:
                self.base_url = self.base_url + '/api/v1'
    
    def check_single(self, lei_code: str, **kwargs) -> Dict[str, Any]:
        """
        Check a single LEI code using GLEIF API.
        
        Args:
            lei_code: LEI code to validate (20 alphanumeric characters)
            **kwargs: Additional options:
                - force_refresh: Skip cache and force API call (default: False)
                - timeout: Request timeout in seconds (default: 15)
                - include_relationships: Include relationship data (default: False)
                
        Returns:
            Dict with validation result and entity information
        """
        start_time = time.time()
        force_refresh = kwargs.get('force_refresh', False)
        request_timeout = kwargs.get('timeout', 15)
        include_relationships = kwargs.get('include_relationships', False)
        
        try:
            # Validate LEI format
            validated_lei = self._validate_lei_format(lei_code)
            
            # Check cache first (unless force refresh)
            cache_key = self._get_cache_key(validated_lei, include_relationships=include_relationships)
            if not force_refresh:
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_result['cached'] = True
                    cached_result['response_time_ms'] = int((time.time() - start_time) * 1000)
                    logger.debug("GLEIF cache hit", lei_code=validated_lei)
                    return cached_result
            
            # Check rate limit before making API call
            if not self._check_rate_limit():
                # If rate limited, try to return cached result even if stale
                stale_result = self._get_cached_result(cache_key)
                if stale_result:
                    stale_result['cached'] = True
                    stale_result['stale'] = True
                    stale_result['warning'] = 'Rate limited - returning cached result'
                    logger.warning("Rate limited, returning stale cache", lei_code=validated_lei)
                    return stale_result
                
                raise RateLimitExceeded(f"Rate limit exceeded for {self.source_name}")
            
            # Make API request with retry logic
            result = self._execute_with_retry(
                self._make_gleif_request, 
                validated_lei,
                include_relationships=include_relationships,
                timeout=request_timeout
            )
            
            # Enhance result with metadata
            result['response_time_ms'] = int((time.time() - start_time) * 1000)
            result['checked_at'] = datetime.utcnow().isoformat() + 'Z'
            result['source'] = self.source_name
            result['cached'] = False
            result['identifier'] = validated_lei
            
            # Cache successful and not_found results (but not errors)
            if result['status'] in ['valid', 'not_found']:
                self._cache_result(cache_key, result)
                logger.info("GLEIF check completed and cached", 
                           lei_code=validated_lei,
                           status=result['status'],
                           response_time=result['response_time_ms'])
            else:
                logger.warning("GLEIF check completed with error - not caching", 
                              lei_code=validated_lei,
                              status=result['status'],
                              error=result.get('error'))
            
            return result
            
        except ValidationError as e:
            error_result = self._create_error_result(lei_code, str(e), 'validation_error')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except RateLimitExceeded as e:
            error_result = self._create_error_result(lei_code, str(e), 'rate_limited')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except DataSourceUnavailable as e:
            error_result = self._create_error_result(lei_code, str(e), 'unavailable')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except Exception as e:
            logger.error("Unexpected error in GLEIF check", 
                        lei_code=lei_code, error=str(e), exc_info=True)
            error_result = self._create_error_result(lei_code, f"Unexpected error: {str(e)}")
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
    
    def check_batch(self, lei_codes: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        Check multiple LEI codes with optimized batch processing.
        
        Args:
            lei_codes: List of LEI codes to check
            **kwargs: Additional options:
                - batch_delay: Delay between requests (default: 0.5 seconds)
                - max_workers: Maximum concurrent workers (default: 5)
                - fail_fast: Stop on first error (default: False)
                - timeout: Timeout per request (default: 15 seconds)
                - include_relationships: Include relationship data (default: False)
            
        Returns:
            List of validation results
        """
        if not lei_codes:
            return []
        
        logger.info("Starting GLEIF batch check", count=len(lei_codes))
        
        # Configuration
        batch_delay = kwargs.get('batch_delay', 0.5)
        max_workers = min(kwargs.get('max_workers', 5), 10)  # GLEIF can handle more concurrent requests
        fail_fast = kwargs.get('fail_fast', False)
        timeout = kwargs.get('timeout', 15)
        include_relationships = kwargs.get('include_relationships', False)
        
        results = []
        failed_count = 0
        
        # Use threading for concurrent requests with rate limiting
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_lei = {}
            for i, lei_code in enumerate(lei_codes):
                # Add staggered delay to respect rate limits
                if i > 0 and batch_delay > 0:
                    time.sleep(batch_delay / max_workers)
                
                future = executor.submit(
                    self._safe_check_single, 
                    lei_code, 
                    timeout=timeout,
                    include_relationships=include_relationships
                )
                future_to_lei[future] = lei_code
            
            # Collect results as they complete
            for future in as_completed(future_to_lei):
                lei_code = future_to_lei[future]
                try:
                    result = future.result(timeout=timeout + 5)  # Extra timeout buffer
                    results.append(result)
                    
                    if result['status'] == 'error':
                        failed_count += 1
                        if fail_fast:
                            logger.warning("Batch processing stopped due to fail_fast", 
                                         lei_code=lei_code)
                            # Cancel remaining futures
                            for remaining_future in future_to_lei:
                                if not remaining_future.done():
                                    remaining_future.cancel()
                            break
                            
                except Exception as e:
                    logger.error("Batch future failed", lei_code=lei_code, error=str(e))
                    failed_count += 1
                    results.append(self._create_error_result(lei_code, f"Future execution failed: {str(e)}"))
                    
                    if fail_fast:
                        break
        
        # Sort results to maintain original order
        lei_to_index = {lei: i for i, lei in enumerate(lei_codes)}
        results.sort(key=lambda r: lei_to_index.get(r.get('identifier', ''), 999))
        
        logger.info("GLEIF batch check completed", 
                   total=len(lei_codes), 
                   successful=len([r for r in results if r['status'] in ['valid', 'not_found']]),
                   failed=failed_count,
                   cached=len([r for r in results if r.get('cached', False)]))
        
        return results
    
    def _safe_check_single(self, lei_code: str, **kwargs) -> Dict[str, Any]:
        """Thread-safe wrapper for check_single with enhanced error handling."""
        try:
            return self.check_single(lei_code, **kwargs)
        except RateLimitExceeded as e:
            logger.warning("Rate limit hit during batch processing", lei_code=lei_code)
            return self._create_error_result(lei_code, str(e), 'rate_limited')
        except DataSourceUnavailable as e:
            logger.warning("GLEIF unavailable during batch processing", lei_code=lei_code)
            return self._create_error_result(lei_code, str(e), 'unavailable')
        except ValidationError as e:
            return self._create_error_result(lei_code, str(e), 'validation_error')
        except Exception as e:
            logger.error("Unexpected error in batch processing", 
                        lei_code=lei_code, error=str(e), exc_info=True)
            return self._create_error_result(lei_code, f"Unexpected error: {str(e)}")
    
    def _validate_lei_format(self, lei_code: str) -> str:
        """
        Validate and clean LEI code format.
        
        Args:
            lei_code: LEI code to validate
            
        Returns:
            Cleaned and validated LEI code
            
        Raises:
            ValidationError: If LEI format is invalid
        """
        if not lei_code:
            raise ValidationError("LEI code cannot be empty")
        
        # Clean LEI code (remove spaces, hyphens, convert to uppercase)
        clean_lei = re.sub(r'[^A-Z0-9]', '', lei_code.upper())
        
        # Validate format (20 alphanumeric characters)
        if not re.match(self.LEI_PATTERN, clean_lei):
            raise ValidationError(f"Invalid LEI format: {lei_code}. LEI must be 20 alphanumeric characters")
        
        # Validate check digits (basic checksum validation)
        if not self._validate_lei_checksum(clean_lei):
            raise ValidationError(f"Invalid LEI checksum: {lei_code}")
        
        return clean_lei
    
    def _validate_lei_checksum(self, lei_code: str) -> bool:
        """
        Validate LEI checksum using ISO 17442 standard.
        
        Args:
            lei_code: 20-character LEI code
            
        Returns:
            True if checksum is valid, False otherwise
        """
        if len(lei_code) != 20:
            return False
        
        # Extract the first 18 characters and the 2-digit check
        lei_base = lei_code[:18]
        check_digits = lei_code[18:20]
        
        try:
            # Convert letters to numbers (A=10, B=11, ..., Z=35)
            numeric_string = ""
            for char in lei_base:
                if char.isdigit():
                    numeric_string += char
                else:
                    numeric_string += str(ord(char) - ord('A') + 10)
            
            # Append check digits
            numeric_string += check_digits
            
            # Calculate mod 97
            remainder = int(numeric_string) % 97
            
            # Valid if remainder is 1
            return remainder == 1
            
        except (ValueError, OverflowError):
            # Handle cases where the number is too large or invalid
            return False
    
    def _make_gleif_request(self, lei_code: str, include_relationships: bool = False, timeout: int = 15) -> Dict[str, Any]:
        """
        Make the actual GLEIF API request.
        
        Args:
            lei_code: LEI code to look up
            include_relationships: Whether to include relationship data
            timeout: Request timeout in seconds
            
        Returns:
            Parsed GLEIF response
        """
        url = f"{self.base_url}{self.LEI_RECORDS_ENDPOINT}/{lei_code}"
        
        # Add query parameters if needed
        params = {}
        if include_relationships:
            params['include'] = 'relationships'
        
        try:
            logger.debug("Making GLEIF request", 
                        lei_code=lei_code, 
                        url=url,
                        timeout=timeout,
                        include_relationships=include_relationships)
            
            response = self.session.get(
                url,
                params=params,
                timeout=timeout
            )
            
            logger.debug("GLEIF response received", 
                        status_code=response.status_code,
                        content_length=len(response.text))
            
            # Handle different HTTP status codes
            if response.status_code == 200:
                return self._parse_gleif_response(response.json(), lei_code)
            elif response.status_code == 404:
                return {
                    'identifier': lei_code,
                    'status': 'not_found',
                    'valid': False,
                    'error': 'LEI code not found in GLEIF database',
                    'lei_code': lei_code
                }
            elif response.status_code == 429:
                raise RateLimitExceeded("GLEIF API rate limit exceeded")
            elif response.status_code in [500, 502, 503, 504]:
                raise DataSourceUnavailable(f"GLEIF API server error: HTTP {response.status_code}")
            elif response.status_code == 400:
                raise ValidationError(f"GLEIF API bad request: HTTP {response.status_code}")
            else:
                raise DataSourceUnavailable(f"GLEIF API returned HTTP {response.status_code}")
            
        except requests.exceptions.Timeout as e:
            logger.warning("GLEIF API timeout", timeout=timeout, error=str(e))
            raise DataSourceUnavailable(f"GLEIF API timeout after {timeout}s")
        except requests.exceptions.ConnectionError as e:
            logger.warning("GLEIF API connection error", error=str(e))
            raise DataSourceUnavailable("Cannot connect to GLEIF API - network issue or service down")
        except requests.exceptions.HTTPError as e:
            logger.warning("GLEIF API HTTP error", error=str(e))
            raise DataSourceUnavailable(f"GLEIF API HTTP error: {str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error("GLEIF API request exception", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"GLEIF API request failed: {str(e)}")
        except (RateLimitExceeded, ValidationError, DataSourceUnavailable):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error("Unexpected error in GLEIF request", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"Unexpected GLEIF API error: {str(e)}")
    
    def _parse_gleif_response(self, response_data: Dict[str, Any], lei_code: str) -> Dict[str, Any]:
        """Parse GLEIF JSON API response."""
        try:
            # GLEIF uses JSON API format
            if 'data' not in response_data:
                raise DataSourceUnavailable('Invalid GLEIF response format - missing data')
            
            data = response_data['data']
            attributes = data.get('attributes', {})
            
            # Extract entity information
            entity = attributes.get('entity', {})
            registration = attributes.get('registration', {})
            
            # Entity details
            legal_name = entity.get('legalName', {}).get('name', 'Name not available')
            legal_form = entity.get('legalForm', {}).get('id')
            status = entity.get('status')
            
            # Registration details
            registration_authority = registration.get('registrationAuthority', {}).get('id')
            registration_authority_name = registration.get('registrationAuthority', {}).get('other')
            
            # Address information
            legal_address = entity.get('legalAddress', {})
            headquarters_address = entity.get('headquartersAddress', {})
            
            # Format addresses
            legal_address_formatted = self._format_address(legal_address)
            headquarters_address_formatted = self._format_address(headquarters_address)
            
            # Determine validity based on status
            is_valid = status in ['ACTIVE', 'INACTIVE']  # Both are considered valid LEI codes
            result_status = 'valid' if is_valid else 'invalid'
            
            result = {
                'identifier': lei_code,
                'status': result_status,
                'valid': is_valid,
                'lei_code': lei_code,
                'entity_status': status,
                'legal_name': legal_name,
                'legal_form': legal_form,
                'registration_authority': registration_authority,
                'registration_authority_name': registration_authority_name,
                'legal_address': legal_address_formatted,
                'headquarters_address': headquarters_address_formatted,
                'data': {
                    'entity': entity,
                    'registration': registration,
                    'raw_attributes': attributes
                }
            }
            
            # Add warning if LEI is inactive
            if status == 'INACTIVE':
                result['warning'] = 'LEI code is inactive but still valid'
            elif status not in ['ACTIVE', 'INACTIVE']:
                result['warning'] = f'LEI status is {status}'
            
            return result
            
        except KeyError as e:
            logger.error("Missing key in GLEIF response", key=str(e), lei_code=lei_code)
            raise DataSourceUnavailable(f'Invalid GLEIF response format - missing key: {str(e)}')
        except Exception as e:
            logger.error("Error parsing GLEIF response", error=str(e), lei_code=lei_code, exc_info=True)
            raise DataSourceUnavailable(f'Error parsing GLEIF response: {str(e)}')
    
    def _format_address(self, address_data: Dict[str, Any]) -> Optional[str]:
        """Format address data into a readable string."""
        if not address_data:
            return None
        
        parts = []
        
        # Add address lines
        for i in range(1, 5):  # addressLines_1 to addressLines_4
            line = address_data.get(f'addressLines_{i}')
            if line:
                parts.append(line)
        
        # Add city
        city = address_data.get('city')
        if city:
            parts.append(city)
        
        # Add region/state
        region = address_data.get('region')
        if region:
            parts.append(region)
        
        # Add postal code
        postal_code = address_data.get('postalCode')
        if postal_code:
            parts.append(postal_code)
        
        # Add country
        country = address_data.get('country')
        if country:
            parts.append(country)
        
        return ', '.join(parts) if parts else None
    
    def validate_lei_format(self, lei_code: str) -> Dict[str, Any]:
        """
        Validate LEI code format without making API call.
        
        Args:
            lei_code: LEI code to validate
            
        Returns:
            Dict with validation result
        """
        try:
            validated_lei = self._validate_lei_format(lei_code)
            return {
                'valid': True,
                'lei_code': validated_lei,
                'message': 'LEI code format is valid'
            }
        except ValidationError as e:
            return {
                'valid': False,
                'error': str(e),
                'message': 'LEI code format is invalid'
            }
    
    def search_by_name(self, entity_name: str, country_code: str = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Search for entities by name using GLEIF API.
        
        Args:
            entity_name: Name of the entity to search for
            country_code: Optional country code filter
            **kwargs: Additional search options:
                - limit: Maximum number of results (default: 10, max: 100)
                - timeout: Request timeout in seconds (default: 15)
                
        Returns:
            List of matching entities
        """
        limit = min(kwargs.get('limit', 10), 100)
        timeout = kwargs.get('timeout', 15)
        
        try:
            # Build search URL
            url = f"{self.base_url}{self.LEI_RECORDS_ENDPOINT}"
            
            # Build query parameters
            params = {
                'filter[entity.legalName]': entity_name,
                'page[size]': limit
            }
            
            if country_code:
                params['filter[entity.legalAddress.country]'] = country_code.upper()
            
            logger.debug("Making GLEIF search request", 
                        entity_name=entity_name, 
                        country_code=country_code,
                        limit=limit)
            
            response = self.session.get(url, params=params, timeout=timeout)
            
            if response.status_code == 200:
                response_data = response.json()
                results = []
                
                for item in response_data.get('data', []):
                    lei_code = item.get('id')
                    if lei_code:
                        # Parse each result using the same logic as single check
                        parsed_result = self._parse_gleif_response({'data': item}, lei_code)
                        results.append(parsed_result)
                
                logger.info("GLEIF search completed", 
                           entity_name=entity_name,
                           results_count=len(results))
                
                return results
            else:
                logger.warning("GLEIF search failed", 
                              status_code=response.status_code,
                              entity_name=entity_name)
                return []
                
        except Exception as e:
            logger.error("Error in GLEIF search", 
                        entity_name=entity_name, 
                        error=str(e), 
                        exc_info=True)
            return []
    
    def get_lei_relationships(self, lei_code: str, **kwargs) -> Dict[str, Any]:
        """
        Get relationship information for a LEI code.
        
        Args:
            lei_code: LEI code to get relationships for
            **kwargs: Additional options:
                - timeout: Request timeout in seconds (default: 15)
                
        Returns:
            Dict with relationship information
        """
        timeout = kwargs.get('timeout', 15)
        
        try:
            validated_lei = self._validate_lei_format(lei_code)
            
            url = f"{self.base_url}/lei-records/{validated_lei}/relationships"
            
            logger.debug("Making GLEIF relationships request", lei_code=validated_lei)
            
            response = self.session.get(url, timeout=timeout)
            
            if response.status_code == 200:
                return {
                    'lei_code': validated_lei,
                    'status': 'success',
                    'relationships': response.json()
                }
            elif response.status_code == 404:
                return {
                    'lei_code': validated_lei,
                    'status': 'not_found',
                    'error': 'No relationships found for this LEI code'
                }
            else:
                return {
                    'lei_code': validated_lei,
                    'status': 'error',
                    'error': f'API returned HTTP {response.status_code}'
                }
                
        except ValidationError as e:
            return {
                'lei_code': lei_code,
                'status': 'validation_error',
                'error': str(e)
            }
        except Exception as e:
            logger.error("Error getting LEI relationships", 
                        lei_code=lei_code, 
                        error=str(e), 
                        exc_info=True)
            return {
                'lei_code': lei_code,
                'status': 'error',
                'error': f'Unexpected error: {str(e)}'
            }