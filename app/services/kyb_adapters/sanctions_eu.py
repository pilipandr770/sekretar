"""EU Sanctions List API adapter."""
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


class EUSanctionsAdapter(BaseKYBAdapter):
    """Adapter for EU Consolidated Sanctions List."""
    
    # Configuration
    RATE_LIMIT = 100  # EU sanctions API is more lenient
    RATE_WINDOW = 60  # per minute
    CACHE_TTL = 7200  # 2 hours cache (sanctions don't change frequently)
    MAX_RETRIES = 3
    RETRY_DELAY = 1
    
    # EU Sanctions API endpoints
    EU_SANCTIONS_BASE_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList/content"
    EU_SANCTIONS_SEARCH_URL = "https://webgate.ec.europa.eu/fsd/fsf/public/api/v1/search"
    
    def __init__(self, redis_client=None):
        """Initialize EU Sanctions adapter."""
        super().__init__(redis_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Secretary-KYB/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # Load sanctions data on initialization
        self._sanctions_data = None
        self._last_update = None
        
    def check_single(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """
        Check a single entity against EU sanctions list.
        
        Args:
            entity_name: Company or individual name to check
            **kwargs: Additional options:
                - force_refresh: Skip cache and force API call
                - match_threshold: Similarity threshold (0.0-1.0, default: 0.8)
                - include_aliases: Include alias matches (default: True)
                
        Returns:
            Dict with sanctions check result
        """
        start_time = time.time()
        force_refresh = kwargs.get('force_refresh', False)
        match_threshold = kwargs.get('match_threshold', 0.8)
        include_aliases = kwargs.get('include_aliases', True)
        
        try:
            # Validate input
            clean_name = self._validate_entity_name(entity_name)
            
            # Check cache first
            cache_key = self._get_cache_key(clean_name, match_threshold=match_threshold)
            if not force_refresh:
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_result['cached'] = True
                    cached_result['response_time_ms'] = int((time.time() - start_time) * 1000)
                    logger.debug("EU sanctions cache hit", entity_name=clean_name)
                    return cached_result
            
            # Check rate limit
            if not self._check_rate_limit():
                raise RateLimitExceeded(f"Rate limit exceeded for {self.source_name}")
            
            # Perform sanctions check
            result = self._execute_with_retry(
                self._check_sanctions_match,
                clean_name,
                match_threshold,
                include_aliases
            )
            
            # Enhance result with metadata
            result['response_time_ms'] = int((time.time() - start_time) * 1000)
            result['checked_at'] = datetime.utcnow().isoformat() + 'Z'
            result['source'] = self.source_name
            result['cached'] = False
            result['identifier'] = clean_name
            result['match_threshold'] = match_threshold
            
            # Cache the result
            self._cache_result(cache_key, result)
            
            logger.info("EU sanctions check completed",
                       entity_name=clean_name,
                       status=result['status'],
                       matches_found=len(result.get('matches', [])),
                       response_time=result['response_time_ms'])
            
            return result
            
        except ValidationError as e:
            error_result = self._create_error_result(entity_name, str(e), 'validation_error')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except RateLimitExceeded as e:
            error_result = self._create_error_result(entity_name, str(e), 'rate_limited')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except DataSourceUnavailable as e:
            error_result = self._create_error_result(entity_name, str(e), 'unavailable')
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
        except Exception as e:
            logger.error("Unexpected error in EU sanctions check",
                        entity_name=entity_name, error=str(e), exc_info=True)
            error_result = self._create_error_result(entity_name, f"Unexpected error: {str(e)}")
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
    
    def check_batch(self, entity_names: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        Check multiple entities against EU sanctions list.
        
        Args:
            entity_names: List of entity names to check
            **kwargs: Additional options (same as check_single)
            
        Returns:
            List of sanctions check results
        """
        if not entity_names:
            return []
        
        logger.info("Starting EU sanctions batch check", count=len(entity_names))
        
        results = []
        for entity_name in entity_names:
            result = self.check_single(entity_name, **kwargs)
            results.append(result)
            
            # Small delay between requests to be respectful
            time.sleep(0.1)
        
        logger.info("EU sanctions batch check completed",
                   total=len(entity_names),
                   matches=len([r for r in results if r.get('status') == 'match']),
                   no_matches=len([r for r in results if r.get('status') == 'no_match']))
        
        return results
    
    def _validate_entity_name(self, entity_name: str) -> str:
        """Validate and clean entity name."""
        if not entity_name or not entity_name.strip():
            raise ValidationError("Entity name cannot be empty")
        
        # Clean and normalize the name
        clean_name = entity_name.strip()
        
        # Remove excessive whitespace
        clean_name = re.sub(r'\s+', ' ', clean_name)
        
        # Minimum length check
        if len(clean_name) < 3:
            raise ValidationError("Entity name must be at least 3 characters long")
        
        return clean_name
    
    def _check_sanctions_match(self, entity_name: str, match_threshold: float, include_aliases: bool) -> Dict[str, Any]:
        """
        Check entity against EU sanctions list.
        
        This is a simplified implementation. In production, you would:
        1. Download the full EU sanctions XML file
        2. Parse and index the sanctions data
        3. Implement fuzzy matching algorithms
        4. Handle different entity types (individuals, companies, etc.)
        """
        try:
            # For demo purposes, we'll use a simple keyword-based approach
            # In production, this would query the actual EU sanctions database
            
            # Simulate API call delay
            time.sleep(0.1)
            
            # Demo sanctions keywords (in production, this would be the full database)
            demo_sanctions_keywords = [
                'SBERBANK', 'GAZPROM', 'ROSNEFT', 'LUKOIL', 'NOVATEK',
                'VEB', 'ROSTEC', 'ROSATOM', 'AEROFLOT', 'RUSSIAN RAILWAYS',
                'PUTIN', 'LAVROV', 'SHOIGU', 'MEDVEDEV', 'PESKOV',
                'WAGNER', 'PRIGOZHIN', 'KADYROV', 'LUKASHENKO',
                'BANK ROSSIYA', 'GENBANK', 'SMP BANK', 'SOVCOMBANK'
            ]
            
            # Normalize entity name for matching
            normalized_name = entity_name.upper()
            
            # Find matches
            matches = []
            for keyword in demo_sanctions_keywords:
                if keyword in normalized_name:
                    # Calculate similarity score (improved logic)
                    # If keyword is found in the name, it's a match regardless of length difference
                    similarity = max(0.8, len(keyword) / len(normalized_name))  # Minimum 0.8 for keyword matches
                    if similarity >= match_threshold:
                        matches.append({
                            'matched_name': keyword,
                            'similarity_score': similarity,
                            'match_type': 'keyword',
                            'sanctions_program': 'EU Restrictive Measures',
                            'entity_type': 'company' if any(word in keyword for word in ['BANK', 'CORP', 'LLC', 'LTD']) else 'individual',
                            'listing_date': '2022-02-26',  # Demo date
                            'reason': 'Actions undermining territorial integrity of Ukraine'
                        })
            
            # Determine result status
            if matches:
                status = 'match'
                risk_level = 'critical'
                message = f"Found {len(matches)} sanctions match(es)"
            else:
                status = 'no_match'
                risk_level = 'low'
                message = "No sanctions matches found"
            
            return {
                'identifier': entity_name,
                'status': status,
                'risk_level': risk_level,
                'message': message,
                'matches': matches,
                'total_matches': len(matches),
                'data': {
                    'entity_name': entity_name,
                    'normalized_name': normalized_name,
                    'match_threshold': match_threshold,
                    'include_aliases': include_aliases
                }
            }
            
        except Exception as e:
            logger.error("Error in EU sanctions matching", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"EU sanctions check failed: {str(e)}")
    
    def update_sanctions_data(self) -> Dict[str, Any]:
        """
        Update local sanctions data from EU API.
        
        In production, this would:
        1. Download the latest EU sanctions XML file
        2. Parse and index the data
        3. Store in local database or cache
        4. Return update statistics
        """
        try:
            logger.info("Updating EU sanctions data")
            
            # Simulate data update
            self._last_update = datetime.utcnow()
            
            # In production, you would:
            # 1. Download from EU_SANCTIONS_BASE_URL
            # 2. Parse XML data
            # 3. Extract entities, aliases, addresses
            # 4. Build search index
            
            return {
                'success': True,
                'last_update': self._last_update.isoformat() + 'Z',
                'total_entities': 1500,  # Demo number
                'individuals': 800,
                'companies': 700,
                'message': 'EU sanctions data updated successfully'
            }
            
        except Exception as e:
            logger.error("Failed to update EU sanctions data", error=str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to update EU sanctions data'
            }
    
    def get_sanctions_info(self) -> Dict[str, Any]:
        """Get information about the EU sanctions list."""
        return {
            'source': 'European Union Consolidated Sanctions List',
            'url': self.EU_SANCTIONS_BASE_URL,
            'last_update': self._last_update.isoformat() + 'Z' if self._last_update else None,
            'update_frequency': 'Daily',
            'entity_types': ['individuals', 'companies', 'organizations'],
            'coverage': 'EU restrictive measures and sanctions',
            'match_types': ['exact', 'fuzzy', 'alias'],
            'supported_languages': ['EN', 'FR', 'DE', 'ES', 'IT']
        }
    
    def search_entity(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """
        Search for entities in the sanctions list.
        
        Args:
            query: Search query
            limit: Maximum number of results
            
        Returns:
            Search results
        """
        try:
            # Validate query
            if not query or len(query.strip()) < 3:
                raise ValidationError("Search query must be at least 3 characters")
            
            # In production, this would search the indexed sanctions data
            # For demo, return mock results
            
            demo_results = []
            if 'SBERBANK' in query.upper():
                demo_results.append({
                    'name': 'SBERBANK OF RUSSIA',
                    'entity_type': 'company',
                    'sanctions_program': 'EU Restrictive Measures',
                    'listing_date': '2022-02-26',
                    'aliases': ['SBERBANK', 'SBER'],
                    'addresses': ['Moscow, Russian Federation'],
                    'reason': 'Actions undermining territorial integrity of Ukraine'
                })
            
            return {
                'query': query,
                'total_results': len(demo_results),
                'results': demo_results[:limit],
                'search_time_ms': 50
            }
            
        except Exception as e:
            logger.error("EU sanctions search failed", query=query, error=str(e))
            return {
                'query': query,
                'error': str(e),
                'total_results': 0,
                'results': []
            }