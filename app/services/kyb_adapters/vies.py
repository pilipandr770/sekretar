"""VIES (VAT Information Exchange System) API adapter."""
import time
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from flask import current_app
import structlog
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

from .base import BaseKYBAdapter, ValidationError, DataSourceUnavailable, RateLimitExceeded

logger = structlog.get_logger()


class VIESAdapter(BaseKYBAdapter):
    """Adapter for VIES VAT validation API."""
    
    # Configuration
    RATE_LIMIT = 30  # VIES has strict rate limits
    RATE_WINDOW = 60  # per minute
    CACHE_TTL = 3600  # 1 hour cache
    MAX_RETRIES = 3  # VIES can be unstable
    RETRY_DELAY = 2  # seconds
    
    # VIES API endpoint
    VIES_URL = "https://ec.europa.eu/taxation_customs/vies/services/checkVatService"
    
    # EU country codes that support VIES
    EU_COUNTRIES = {
        'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES', 
        'FI', 'FR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT', 
        'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK'
    }
    
    # VAT number patterns for validation
    VAT_PATTERNS = {
        'AT': r'^U\d{8}$',
        'BE': r'^\d{10}$',
        'BG': r'^\d{9,10}$',
        'CY': r'^\d{8}[A-Z]$',
        'CZ': r'^\d{8,10}$',
        'DE': r'^\d{9}$',
        'DK': r'^\d{8}$',
        'EE': r'^\d{9}$',
        'EL': r'^\d{9}$',
        'ES': r'^[A-Z]\d{7}[A-Z]$|^\d{8}[A-Z]$|^[A-Z]\d{8}$',
        'FI': r'^\d{8}$',
        'FR': r'^[A-Z]{2}\d{9}$|^\d{11}$',
        'HR': r'^\d{11}$',
        'HU': r'^\d{8}$',
        'IE': r'^\d[A-Z\d]\d{5}[A-Z]$|^\d{7}[A-Z]{2}$',
        'IT': r'^\d{11}$',
        'LT': r'^\d{9}$|^\d{12}$',
        'LU': r'^\d{8}$',
        'LV': r'^\d{11}$',
        'MT': r'^\d{8}$',
        'NL': r'^\d{9}B\d{2}$',
        'PL': r'^\d{10}$',
        'PT': r'^\d{9}$',
        'RO': r'^\d{2,10}$',
        'SE': r'^\d{12}$',
        'SI': r'^\d{8}$',
        'SK': r'^\d{10}$'
    }
    
    def __init__(self, redis_client=None):
        """Initialize VIES adapter."""
        super().__init__(redis_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Secretary-KYB/1.0',
            'Content-Type': 'text/xml; charset=utf-8',
            'SOAPAction': ''
        })
    
    def check_single(self, vat_number: str, country_code: str = None, **kwargs) -> Dict[str, Any]:
        """
        Check a single VAT number using VIES API with enhanced caching and error handling.
        
        Args:
            vat_number: VAT number to check (with or without country prefix)
            country_code: Optional country code if not included in VAT number
            **kwargs: Additional options:
                - force_refresh: Skip cache and force API call (default: False)
                - timeout: Request timeout in seconds (default: 15)
                
        Returns:
            Dict with validation result
        """
        start_time = time.time()
        force_refresh = kwargs.get('force_refresh', False)
        request_timeout = kwargs.get('timeout', 15)
        
        try:
            # Parse and validate VAT number
            parsed_country, parsed_vat = self._parse_vat_number(vat_number, country_code)
            full_vat = f"{parsed_country}{parsed_vat}"
            
            # Check cache first (unless force refresh)
            cache_key = self._get_cache_key(full_vat)
            if not force_refresh:
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_result['cached'] = True
                    cached_result['response_time_ms'] = int((time.time() - start_time) * 1000)
                    logger.debug("VIES cache hit", vat_number=full_vat)
                    return cached_result
            
            # Check rate limit before making API call
            if not self._check_rate_limit():
                # If rate limited, try to return cached result even if stale
                stale_result = self._get_cached_result(cache_key)
                if stale_result:
                    stale_result['cached'] = True
                    stale_result['stale'] = True
                    stale_result['warning'] = 'Rate limited - returning cached result'
                    logger.warning("Rate limited, returning stale cache", vat_number=full_vat)
                    return stale_result
                
                raise RateLimitExceeded(f"Rate limit exceeded for {self.source_name}")
            
            # Make API request with retry logic
            result = self._execute_with_retry(
                self._make_vies_request, 
                parsed_country, 
                parsed_vat,
                timeout=request_timeout
            )
            
            # Enhance result with metadata
            result['response_time_ms'] = int((time.time() - start_time) * 1000)
            result['checked_at'] = datetime.utcnow().isoformat() + 'Z'
            result['source'] = self.source_name
            result['cached'] = False
            result['identifier'] = full_vat
            
            # Cache successful and invalid results (but not errors)
            if result['status'] in ['valid', 'invalid']:
                self._cache_result(cache_key, result)
                logger.info("VIES check completed and cached", 
                           vat_number=full_vat,
                           status=result['status'],
                           response_time=result['response_time_ms'])
            else:
                logger.warning("VIES check completed with error - not caching", 
                              vat_number=full_vat,
                              status=result['status'],
                              error=result.get('error'))
            
            return result
            
        except ValidationError as e:
            error_result = self._create_error_result(vat_number, str(e), 'validation_error')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except RateLimitExceeded as e:
            error_result = self._create_error_result(vat_number, str(e), 'rate_limited')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except DataSourceUnavailable as e:
            error_result = self._create_error_result(vat_number, str(e), 'unavailable')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except Exception as e:
            logger.error("Unexpected error in VIES check", 
                        vat_number=vat_number, error=str(e), exc_info=True)
            error_result = self._create_error_result(vat_number, f"Unexpected error: {str(e)}")
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
    
    def check_batch(self, vat_numbers: List[str], country_code: str = None, **kwargs) -> List[Dict[str, Any]]:
        """
        Check multiple VAT numbers with optimized batch processing.
        
        Args:
            vat_numbers: List of VAT numbers to check
            country_code: Optional default country code
            **kwargs: Additional options:
                - batch_delay: Delay between requests (default: 1 second)
                - max_workers: Maximum concurrent workers (default: 3)
                - fail_fast: Stop on first error (default: False)
                - timeout: Timeout per request (default: 15 seconds)
            
        Returns:
            List of validation results
        """
        if not vat_numbers:
            return []
        
        logger.info("Starting VIES batch check", count=len(vat_numbers))
        
        # Configuration
        batch_delay = kwargs.get('batch_delay', 1.0)
        max_workers = min(kwargs.get('max_workers', 3), 5)  # Limit to avoid overwhelming VIES
        fail_fast = kwargs.get('fail_fast', False)
        timeout = kwargs.get('timeout', 15)
        
        results = []
        failed_count = 0
        
        # Use threading for concurrent requests with rate limiting
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_vat = {}
            for i, vat_number in enumerate(vat_numbers):
                # Add staggered delay to respect rate limits
                if i > 0 and batch_delay > 0:
                    time.sleep(batch_delay / max_workers)
                
                future = executor.submit(
                    self._safe_check_single, 
                    vat_number, 
                    country_code, 
                    timeout
                )
                future_to_vat[future] = vat_number
            
            # Collect results as they complete
            for future in as_completed(future_to_vat):
                vat_number = future_to_vat[future]
                try:
                    result = future.result(timeout=timeout + 5)  # Extra timeout buffer
                    results.append(result)
                    
                    if result['status'] == 'error':
                        failed_count += 1
                        if fail_fast:
                            logger.warning("Batch processing stopped due to fail_fast", 
                                         vat_number=vat_number)
                            # Cancel remaining futures
                            for remaining_future in future_to_vat:
                                if not remaining_future.done():
                                    remaining_future.cancel()
                            break
                            
                except Exception as e:
                    logger.error("Batch future failed", vat_number=vat_number, error=str(e))
                    failed_count += 1
                    results.append(self._create_error_result(vat_number, f"Future execution failed: {str(e)}"))
                    
                    if fail_fast:
                        break
        
        # Sort results to maintain original order
        vat_to_index = {vat: i for i, vat in enumerate(vat_numbers)}
        results.sort(key=lambda r: vat_to_index.get(r.get('identifier', '').replace(r.get('country_code', ''), ''), 999))
        
        logger.info("VIES batch check completed", 
                   total=len(vat_numbers), 
                   successful=len([r for r in results if r['status'] in ['valid', 'invalid']]),
                   failed=failed_count,
                   cached=len([r for r in results if r.get('cached', False)]))
        
        return results
    
    def _safe_check_single(self, vat_number: str, country_code: str = None, timeout: int = 15) -> Dict[str, Any]:
        """
        Thread-safe wrapper for check_single with enhanced error handling.
        
        Args:
            vat_number: VAT number to check
            country_code: Optional country code
            timeout: Request timeout in seconds
            
        Returns:
            Validation result dictionary
        """
        try:
            # Set timeout for this specific request
            original_timeout = getattr(self.session, 'timeout', None)
            self.session.timeout = timeout
            
            result = self.check_single(vat_number, country_code)
            
            # Restore original timeout
            if original_timeout:
                self.session.timeout = original_timeout
            
            return result
            
        except RateLimitExceeded as e:
            logger.warning("Rate limit hit during batch processing", vat_number=vat_number)
            return self._create_error_result(vat_number, str(e), 'rate_limited')
        except DataSourceUnavailable as e:
            logger.warning("VIES unavailable during batch processing", vat_number=vat_number)
            return self._create_error_result(vat_number, str(e), 'unavailable')
        except ValidationError as e:
            return self._create_error_result(vat_number, str(e), 'validation_error')
        except Exception as e:
            logger.error("Unexpected error in batch processing", 
                        vat_number=vat_number, error=str(e), exc_info=True)
            return self._create_error_result(vat_number, f"Unexpected error: {str(e)}")
    
    def _parse_vat_number(self, vat_number: str, country_code: str = None) -> tuple[str, str]:
        """
        Parse and validate VAT number format.
        
        Returns:
            Tuple of (country_code, vat_number)
        """
        if not vat_number:
            raise ValidationError("VAT number cannot be empty")
        
        # Clean VAT number
        clean_vat = re.sub(r'[^A-Z0-9]', '', vat_number.upper())
        
        # Try to extract country code from VAT number
        extracted_country = None
        extracted_vat = clean_vat
        
        # Check if VAT number starts with a country code
        for country in self.EU_COUNTRIES:
            if clean_vat.startswith(country):
                extracted_country = country
                extracted_vat = clean_vat[len(country):]
                break
        
        # Determine final country code
        final_country = extracted_country or country_code
        if not final_country:
            raise ValidationError("Country code must be provided or included in VAT number")
        
        final_country = final_country.upper()
        
        # Validate country code
        if final_country not in self.EU_COUNTRIES:
            raise ValidationError(f"Country code {final_country} is not supported by VIES")
        
        # Validate VAT number format for the country
        if final_country in self.VAT_PATTERNS:
            pattern = self.VAT_PATTERNS[final_country]
            if not re.match(pattern, extracted_vat):
                raise ValidationError(f"Invalid VAT number format for {final_country}: {extracted_vat}")
        
        return final_country, extracted_vat
    
    def _make_vies_request(self, country_code: str, vat_number: str, timeout: int = 15) -> Dict[str, Any]:
        """
        Make the actual VIES SOAP request with enhanced error handling.
        
        Args:
            country_code: EU country code
            vat_number: VAT number without country prefix
            timeout: Request timeout in seconds
            
        Returns:
            Parsed VIES response
        """
        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
    <soap:Header></soap:Header>
    <soap:Body>
        <tns1:checkVat>
            <tns1:countryCode>{country_code}</tns1:countryCode>
            <tns1:vatNumber>{vat_number}</tns1:vatNumber>
        </tns1:checkVat>
    </soap:Body>
</soap:Envelope>"""
        
        try:
            logger.debug("Making VIES request", 
                        country_code=country_code, 
                        vat_number=vat_number,
                        timeout=timeout)
            
            response = self.session.post(
                self.VIES_URL,
                data=soap_body,
                timeout=timeout,
                headers={
                    'Content-Type': 'text/xml; charset=utf-8',
                    'SOAPAction': '',
                    'User-Agent': 'AI-Secretary-KYB/1.0'
                }
            )
            
            logger.debug("VIES response received", 
                        status_code=response.status_code,
                        content_length=len(response.text))
            
            # Handle different HTTP status codes
            if response.status_code == 200:
                return self._parse_vies_response(response.text, country_code, vat_number)
            elif response.status_code == 429:
                raise RateLimitExceeded("VIES API rate limit exceeded")
            elif response.status_code in [500, 502, 503, 504]:
                raise DataSourceUnavailable(f"VIES API server error: HTTP {response.status_code}")
            elif response.status_code == 400:
                raise ValidationError(f"VIES API bad request: HTTP {response.status_code}")
            else:
                raise DataSourceUnavailable(f"VIES API returned HTTP {response.status_code}")
            
        except requests.exceptions.Timeout as e:
            logger.warning("VIES API timeout", timeout=timeout, error=str(e))
            raise DataSourceUnavailable(f"VIES API timeout after {timeout}s - service may be overloaded")
        except requests.exceptions.ConnectionError as e:
            logger.warning("VIES API connection error", error=str(e))
            raise DataSourceUnavailable("Cannot connect to VIES API - network issue or service down")
        except requests.exceptions.HTTPError as e:
            logger.warning("VIES API HTTP error", error=str(e))
            raise DataSourceUnavailable(f"VIES API HTTP error: {str(e)}")
        except requests.exceptions.RequestException as e:
            logger.error("VIES API request exception", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"VIES API request failed: {str(e)}")
        except (RateLimitExceeded, ValidationError, DataSourceUnavailable):
            # Re-raise our custom exceptions
            raise
        except Exception as e:
            logger.error("Unexpected error in VIES request", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"Unexpected VIES API error: {str(e)}")
    
    def _parse_vies_response(self, response_text: str, country_code: str, vat_number: str) -> Dict[str, Any]:
        """Parse VIES SOAP response."""
        # Check for SOAP fault first
        if 'soap:Fault' in response_text or 'faultstring' in response_text:
            fault_msg = self._extract_xml_value(response_text, 'faultstring') or 'SOAP fault'
            
            # Handle specific VIES errors
            if 'INVALID_INPUT' in fault_msg:
                return {
                    'identifier': f"{country_code}{vat_number}",
                    'status': 'invalid',
                    'valid': False,
                    'error': 'Invalid VAT number format',
                    'country_code': country_code,
                    'vat_number': vat_number
                }
            elif 'SERVICE_UNAVAILABLE' in fault_msg:
                raise DataSourceUnavailable('VIES service temporarily unavailable')
            elif 'MS_UNAVAILABLE' in fault_msg:
                raise DataSourceUnavailable(f'VIES service for {country_code} temporarily unavailable')
            else:
                raise DataSourceUnavailable(f'VIES SOAP fault: {fault_msg}')
        
        # Parse successful response
        if 'valid>true</valid' in response_text:
            # Extract company information
            name = self._extract_xml_value(response_text, 'name')
            address = self._extract_xml_value(response_text, 'address')
            
            # Clean up extracted data
            if name:
                name = re.sub(r'\s+', ' ', name.replace('\n', ' ')).strip()
            if address:
                address = re.sub(r'\s+', ' ', address.replace('\n', ' ')).strip()
            
            return {
                'identifier': f"{country_code}{vat_number}",
                'status': 'valid',
                'valid': True,
                'country_code': country_code,
                'vat_number': vat_number,
                'full_vat_number': f"{country_code}{vat_number}",
                'company_name': name or 'Name not available',
                'company_address': address or 'Address not available',
                'data': {
                    'name': name,
                    'address': address,
                    'country_code': country_code,
                    'vat_number': vat_number
                }
            }
        elif 'valid>false</valid' in response_text:
            return {
                'identifier': f"{country_code}{vat_number}",
                'status': 'invalid',
                'valid': False,
                'error': 'VAT number not found in VIES database',
                'country_code': country_code,
                'vat_number': vat_number,
                'full_vat_number': f"{country_code}{vat_number}"
            }
        else:
            raise DataSourceUnavailable('Unexpected VIES response format')
    
    def _extract_xml_value(self, xml_content: str, tag: str) -> Optional[str]:
        """Extract value from XML content."""
        start_tag = f'<{tag}>'
        end_tag = f'</{tag}>'
        
        start_index = xml_content.find(start_tag)
        if start_index == -1:
            return None
        
        start_index += len(start_tag)
        end_index = xml_content.find(end_tag, start_index)
        
        if end_index == -1:
            return None
        
        return xml_content[start_index:end_index].strip()
    
    def validate_vat_format(self, vat_number: str, country_code: str = None) -> Dict[str, Any]:
        """
        Validate VAT number format without making API call.
        
        Returns:
            Dict with validation result
        """
        try:
            country, vat = self._parse_vat_number(vat_number, country_code)
            return {
                'valid': True,
                'country_code': country,
                'vat_number': vat,
                'full_vat_number': f"{country}{vat}",
                'message': 'VAT number format is valid'
            }
        except ValidationError as e:
            return {
                'valid': False,
                'error': str(e),
                'message': 'VAT number format is invalid'
            }
    
    def get_supported_countries(self) -> List[Dict[str, str]]:
        """Get list of countries supported by VIES."""
        return [
            {'code': code, 'name': self._get_country_name(code)} 
            for code in sorted(self.EU_COUNTRIES)
        ]
    
    def _get_country_name(self, country_code: str) -> str:
        """Get country name from country code."""
        country_names = {
            'AT': 'Austria', 'BE': 'Belgium', 'BG': 'Bulgaria', 'CY': 'Cyprus',
            'CZ': 'Czech Republic', 'DE': 'Germany', 'DK': 'Denmark', 'EE': 'Estonia',
            'EL': 'Greece', 'ES': 'Spain', 'FI': 'Finland', 'FR': 'France',
            'HR': 'Croatia', 'HU': 'Hungary', 'IE': 'Ireland', 'IT': 'Italy',
            'LT': 'Lithuania', 'LU': 'Luxembourg', 'LV': 'Latvia', 'MT': 'Malta',
            'NL': 'Netherlands', 'PL': 'Poland', 'PT': 'Portugal', 'RO': 'Romania',
            'SE': 'Sweden', 'SI': 'Slovenia', 'SK': 'Slovakia'
        }
        return country_names.get(country_code, country_code)
    
    def check_batch_optimized(self, vat_data: List[Dict[str, str]], **kwargs) -> List[Dict[str, Any]]:
        """
        Optimized batch checking with intelligent caching and error recovery.
        
        Args:
            vat_data: List of dicts with 'vat_number' and optional 'country_code'
            **kwargs: Batch processing options
            
        Returns:
            List of validation results with enhanced metadata
        """
        if not vat_data:
            return []
        
        logger.info("Starting optimized VIES batch check", count=len(vat_data))
        
        # Separate cached and uncached items
        cached_results = []
        uncached_items = []
        
        for item in vat_data:
            vat_number = item.get('vat_number', '')
            country_code = item.get('country_code')
            
            try:
                parsed_country, parsed_vat = self._parse_vat_number(vat_number, country_code)
                full_vat = f"{parsed_country}{parsed_vat}"
                cache_key = self._get_cache_key(full_vat)
                
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_result['cached'] = True
                    cached_results.append((item, cached_result))
                else:
                    uncached_items.append((item, parsed_country, parsed_vat))
                    
            except ValidationError as e:
                error_result = self._create_error_result(vat_number, str(e), 'validation_error')
                cached_results.append((item, error_result))
        
        logger.info("Cache analysis complete", 
                   total=len(vat_data),
                   cached=len(cached_results),
                   uncached=len(uncached_items))
        
        # Process uncached items
        uncached_results = []
        if uncached_items:
            # Convert to simple list for existing batch method
            vat_list = [f"{country}{vat}" for _, country, vat in uncached_items]
            batch_results = self.check_batch(vat_list, **kwargs)
            
            # Match results back to original items
            for i, (item, country, vat) in enumerate(uncached_items):
                if i < len(batch_results):
                    uncached_results.append((item, batch_results[i]))
        
        # Combine and sort results
        all_results = cached_results + uncached_results
        
        # Sort by original order
        item_to_index = {id(item): i for i, item in enumerate(vat_data)}
        all_results.sort(key=lambda x: item_to_index.get(id(x[0]), 999))
        
        # Extract just the results
        final_results = [result for _, result in all_results]
        
        logger.info("Optimized batch check completed",
                   total=len(final_results),
                   cached=len(cached_results),
                   api_calls=len(uncached_items))
        
        return final_results
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get detailed cache statistics for VIES adapter."""
        base_stats = self.get_stats()
        
        if not self.redis_client:
            return {**base_stats, 'cache_stats': 'Redis not available'}
        
        try:
            # Get cache keys for this adapter
            cache_pattern = f"kyb_cache:*{self.source_name}*"
            cache_keys = self.redis_client.keys(cache_pattern)
            
            # Analyze cache contents
            valid_cached = 0
            invalid_cached = 0
            error_cached = 0
            
            for key in cache_keys[:100]:  # Sample first 100 keys
                try:
                    import json
                    cached_data = self.redis_client.get(key)
                    if cached_data:
                        result = json.loads(cached_data)
                        status = result.get('status', 'unknown')
                        if status == 'valid':
                            valid_cached += 1
                        elif status == 'invalid':
                            invalid_cached += 1
                        else:
                            error_cached += 1
                except:
                    continue
            
            cache_stats = {
                'total_cached_items': len(cache_keys),
                'sampled_items': min(100, len(cache_keys)),
                'valid_cached': valid_cached,
                'invalid_cached': invalid_cached,
                'error_cached': error_cached,
                'cache_hit_ratio': 'Not available'  # Would need request tracking
            }
            
            return {**base_stats, 'cache_stats': cache_stats}
            
        except Exception as e:
            logger.error("Failed to get cache stats", error=str(e))
            return {**base_stats, 'cache_stats': f'Error: {str(e)}'}
    
    def clear_cache(self, pattern: str = None) -> Dict[str, Any]:
        """
        Clear VIES cache entries.
        
        Args:
            pattern: Optional pattern to match specific entries
            
        Returns:
            Dict with clearing results
        """
        if not self.redis_client:
            return {'error': 'Redis not available'}
        
        try:
            if pattern:
                cache_pattern = f"kyb_cache:*{pattern}*"
            else:
                cache_pattern = f"kyb_cache:*{self.source_name}*"
            
            keys = self.redis_client.keys(cache_pattern)
            
            if keys:
                deleted = self.redis_client.delete(*keys)
                logger.info("Cache cleared", pattern=cache_pattern, deleted=deleted)
                return {
                    'success': True,
                    'pattern': cache_pattern,
                    'keys_found': len(keys),
                    'keys_deleted': deleted
                }
            else:
                return {
                    'success': True,
                    'pattern': cache_pattern,
                    'keys_found': 0,
                    'keys_deleted': 0,
                    'message': 'No matching cache entries found'
                }
                
        except Exception as e:
            logger.error("Failed to clear cache", error=str(e))
            return {'error': f'Cache clear failed: {str(e)}'}
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check of VIES service.
        
        Returns:
            Dict with health status
        """
        start_time = time.time()
        
        try:
            # Test with a known valid VAT number (European Commission)
            test_result = self.check_single('BE0123456749', force_refresh=True)
            response_time = int((time.time() - start_time) * 1000)
            
            if test_result['status'] in ['valid', 'invalid']:
                return {
                    'status': 'healthy',
                    'response_time_ms': response_time,
                    'test_result': test_result['status'],
                    'message': 'VIES API is responding normally'
                }
            else:
                return {
                    'status': 'degraded',
                    'response_time_ms': response_time,
                    'error': test_result.get('error', 'Unknown error'),
                    'message': 'VIES API returned error for test request'
                }
                
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            return {
                'status': 'unhealthy',
                'response_time_ms': response_time,
                'error': str(e),
                'message': 'VIES API health check failed'
            }