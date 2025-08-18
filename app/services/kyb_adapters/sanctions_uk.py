"""UK HM Treasury Sanctions List API adapter."""
import time
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from flask import current_app
import structlog
import json

from .base import BaseKYBAdapter, ValidationError, DataSourceUnavailable, RateLimitExceeded

logger = structlog.get_logger()


class UKSanctionsAdapter(BaseKYBAdapter):
    """Adapter for UK HM Treasury Consolidated Sanctions List."""
    
    # Configuration
    RATE_LIMIT = 60  # UK sanctions API moderate limits
    RATE_WINDOW = 60  # per minute
    CACHE_TTL = 7200  # 2 hours cache
    MAX_RETRIES = 3
    RETRY_DELAY = 1.5
    
    # UK Sanctions API endpoints
    UK_SANCTIONS_BASE_URL = "https://ofsistorage.blob.core.windows.net/publishlive/2022format"
    UK_CONSOLIDATED_LIST_URL = f"{UK_SANCTIONS_BASE_URL}/ConList.json"
    UK_FINANCIAL_SANCTIONS_URL = "https://assets.publishing.service.gov.uk/government/uploads/system/uploads/attachment_data/file/current/ConList.json"
    
    def __init__(self, redis_client=None):
        """Initialize UK Sanctions adapter."""
        super().__init__(redis_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Secretary-KYB/1.0',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
        
        # UK sanctions data cache
        self._sanctions_data = None
        self._last_update = None
    
    def check_single(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """
        Check a single entity against UK sanctions list.
        
        Args:
            entity_name: Company or individual name to check
            **kwargs: Additional options:
                - force_refresh: Skip cache and force API call
                - match_threshold: Similarity threshold (0.0-1.0, default: 0.8)
                - include_aliases: Include alias matches (default: True)
                - regimes: List of specific UK sanctions regimes to check
                
        Returns:
            Dict with UK sanctions check result
        """
        start_time = time.time()
        force_refresh = kwargs.get('force_refresh', False)
        match_threshold = kwargs.get('match_threshold', 0.8)
        include_aliases = kwargs.get('include_aliases', True)
        regimes = kwargs.get('regimes', None)  # None means all regimes
        
        try:
            # Validate input
            clean_name = self._validate_entity_name(entity_name)
            
            # Check cache first
            cache_key = self._get_cache_key(clean_name, 
                                          match_threshold=match_threshold,
                                          regimes=regimes)
            if not force_refresh:
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_result['cached'] = True
                    cached_result['response_time_ms'] = int((time.time() - start_time) * 1000)
                    logger.debug("UK sanctions cache hit", entity_name=clean_name)
                    return cached_result
            
            # Check rate limit
            if not self._check_rate_limit():
                raise RateLimitExceeded(f"Rate limit exceeded for {self.source_name}")
            
            # Perform UK sanctions check
            result = self._execute_with_retry(
                self._check_uk_sanctions,
                clean_name,
                match_threshold,
                include_aliases,
                regimes
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
            
            logger.info("UK sanctions check completed",
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
            logger.error("Unexpected error in UK sanctions check",
                        entity_name=entity_name, error=str(e), exc_info=True)
            error_result = self._create_error_result(entity_name, f"Unexpected error: {str(e)}")
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
    
    def check_batch(self, entity_names: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        Check multiple entities against UK sanctions list.
        
        Args:
            entity_names: List of entity names to check
            **kwargs: Additional options (same as check_single)
            
        Returns:
            List of UK sanctions check results
        """
        if not entity_names:
            return []
        
        logger.info("Starting UK sanctions batch check", count=len(entity_names))
        
        results = []
        for entity_name in entity_names:
            result = self.check_single(entity_name, **kwargs)
            results.append(result)
            
            # Small delay between requests
            time.sleep(0.1)
        
        logger.info("UK sanctions batch check completed",
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
    
    def _check_uk_sanctions(self, entity_name: str, match_threshold: float, 
                           include_aliases: bool, regimes: Optional[List[str]]) -> Dict[str, Any]:
        """
        Check entity against UK sanctions list.
        
        This is a simplified implementation. In production, you would:
        1. Download and parse the UK Consolidated List JSON
        2. Implement sophisticated matching algorithms
        3. Handle different entity types and regimes
        4. Process aliases and alternate spellings
        """
        try:
            # Simulate API call delay
            time.sleep(0.12)
            
            # Demo UK sanctions data (in production, this would be the full consolidated list)
            demo_uk_sanctions = [
                {
                    'name': 'SBERBANK OF RUSSIA',
                    'aliases': ['SBERBANK', 'SBER', 'SBERBANK ROSSII'],
                    'regime': 'Russia',
                    'entity_type': 'Entity',
                    'unique_id': 'RUS0001',
                    'listing_date': '2022-02-26',
                    'uk_sanctions_list_ref': 'RUS0001',
                    'sanctions_imposed': ['Asset freeze', 'Investment ban']
                },
                {
                    'name': 'GAZPROM PJSC',
                    'aliases': ['GAZPROM', 'GAZPROM OAO'],
                    'regime': 'Russia',
                    'entity_type': 'Entity',
                    'unique_id': 'RUS0002',
                    'listing_date': '2022-02-26',
                    'uk_sanctions_list_ref': 'RUS0002',
                    'sanctions_imposed': ['Asset freeze', 'Investment ban']
                },
                {
                    'name': 'VLADIMIR VLADIMIROVICH PUTIN',
                    'aliases': ['PUTIN', 'VLADIMIR PUTIN', 'V. PUTIN'],
                    'regime': 'Russia',
                    'entity_type': 'Individual',
                    'unique_id': 'RUS0003',
                    'listing_date': '2022-02-25',
                    'uk_sanctions_list_ref': 'RUS0003',
                    'sanctions_imposed': ['Asset freeze', 'Travel ban']
                },
                {
                    'name': 'ROSNEFT OIL COMPANY',
                    'aliases': ['ROSNEFT', 'ROSNEFT PJSC'],
                    'regime': 'Russia',
                    'entity_type': 'Entity',
                    'unique_id': 'RUS0004',
                    'listing_date': '2022-02-26',
                    'uk_sanctions_list_ref': 'RUS0004',
                    'sanctions_imposed': ['Asset freeze', 'Investment ban']
                }
            ]
            
            # Normalize entity name for matching
            normalized_name = entity_name.upper()
            
            # Find matches
            matches = []
            for entry in demo_uk_sanctions:
                # Check if specific regimes are requested
                if regimes and entry['regime'] not in regimes:
                    continue
                
                # Check main name
                if entry['name'] in normalized_name or normalized_name in entry['name']:
                    similarity = self._calculate_similarity(normalized_name, entry['name'])
                    if similarity >= match_threshold:
                        matches.append({
                            'matched_name': entry['name'],
                            'similarity_score': similarity,
                            'match_type': 'primary_name',
                            'uk_unique_id': entry['unique_id'],
                            'sanctions_regime': entry['regime'],
                            'entity_type': entry['entity_type'],
                            'listing_date': entry['listing_date'],
                            'sanctions_list_ref': entry['uk_sanctions_list_ref'],
                            'sanctions_imposed': entry['sanctions_imposed'],
                            'aliases': entry['aliases']
                        })
                
                # Check aliases if enabled
                if include_aliases:
                    for alias in entry['aliases']:
                        if alias in normalized_name or normalized_name in alias:
                            similarity = self._calculate_similarity(normalized_name, alias)
                            if similarity >= match_threshold:
                                matches.append({
                                    'matched_name': alias,
                                    'primary_name': entry['name'],
                                    'similarity_score': similarity,
                                    'match_type': 'alias',
                                    'uk_unique_id': entry['unique_id'],
                                    'sanctions_regime': entry['regime'],
                                    'entity_type': entry['entity_type'],
                                    'listing_date': entry['listing_date'],
                                    'sanctions_list_ref': entry['uk_sanctions_list_ref'],
                                    'sanctions_imposed': entry['sanctions_imposed']
                                })
            
            # Remove duplicates based on UK unique ID
            unique_matches = []
            seen_ids = set()
            for match in matches:
                uid = match['uk_unique_id']
                if uid not in seen_ids:
                    unique_matches.append(match)
                    seen_ids.add(uid)
            
            # Determine result status
            if unique_matches:
                status = 'match'
                risk_level = 'critical'
                message = f"Found {len(unique_matches)} UK sanctions match(es)"
            else:
                status = 'no_match'
                risk_level = 'low'
                message = "No UK sanctions matches found"
            
            return {
                'identifier': entity_name,
                'status': status,
                'risk_level': risk_level,
                'message': message,
                'matches': unique_matches,
                'total_matches': len(unique_matches),
                'regimes_checked': regimes or ['ALL'],
                'data': {
                    'entity_name': entity_name,
                    'normalized_name': normalized_name,
                    'match_threshold': match_threshold,
                    'include_aliases': include_aliases
                }
            }
            
        except Exception as e:
            logger.error("Error in UK sanctions matching", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"UK sanctions check failed: {str(e)}")
    
    def _calculate_similarity(self, name1: str, name2: str) -> float:
        """
        Calculate similarity between two names.
        
        This is a simplified implementation. In production, you would use
        more sophisticated algorithms like Levenshtein distance, Jaro-Winkler, etc.
        """
        # Simple containment-based similarity
        shorter = min(name1, name2, key=len)
        longer = max(name1, name2, key=len)
        
        if shorter in longer:
            return len(shorter) / len(longer)
        
        # Count common words
        words1 = set(name1.split())
        words2 = set(name2.split())
        common_words = words1.intersection(words2)
        
        if not words1 or not words2:
            return 0.0
        
        return len(common_words) / max(len(words1), len(words2))
    
    def update_sanctions_data(self) -> Dict[str, Any]:
        """
        Update local UK sanctions data.
        
        In production, this would:
        1. Download the latest UK Consolidated List JSON
        2. Parse and index the data
        3. Store in local database or cache
        4. Return update statistics
        """
        try:
            logger.info("Updating UK sanctions data")
            
            # Simulate data update
            self._last_update = datetime.utcnow()
            
            # In production, you would:
            # 1. Download from UK_CONSOLIDATED_LIST_URL
            # 2. Parse JSON data
            # 3. Extract entities, aliases, addresses, regimes
            # 4. Build search index
            
            return {
                'success': True,
                'last_update': self._last_update.isoformat() + 'Z',
                'total_entities': 1800,  # Demo number
                'individuals': 1200,
                'entities': 600,
                'regimes': 25,
                'message': 'UK sanctions data updated successfully'
            }
            
        except Exception as e:
            logger.error("Failed to update UK sanctions data", error=str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to update UK sanctions data'
            }
    
    def get_sanctions_regimes(self) -> List[Dict[str, Any]]:
        """Get list of UK sanctions regimes."""
        # Demo regimes - in production, this would be extracted from the consolidated list
        return [
            {
                'code': 'Russia',
                'name': 'Russia',
                'description': 'Sanctions relating to Russia'
            },
            {
                'code': 'Belarus',
                'name': 'Belarus',
                'description': 'Sanctions relating to Belarus'
            },
            {
                'code': 'Iran',
                'name': 'Iran',
                'description': 'Sanctions relating to Iran'
            },
            {
                'code': 'Syria',
                'name': 'Syria',
                'description': 'Sanctions relating to Syria'
            },
            {
                'code': 'Myanmar',
                'name': 'Myanmar',
                'description': 'Sanctions relating to Myanmar'
            },
            {
                'code': 'Afghanistan',
                'name': 'Afghanistan',
                'description': 'Sanctions relating to Afghanistan'
            },
            {
                'code': 'Global Anti-Corruption',
                'name': 'Global Anti-Corruption',
                'description': 'Global Anti-Corruption sanctions'
            },
            {
                'code': 'Global Human Rights',
                'name': 'Global Human Rights',
                'description': 'Global Human Rights sanctions'
            }
        ]
    
    def get_sanctions_info(self) -> Dict[str, Any]:
        """Get information about the UK sanctions list."""
        return {
            'source': 'UK HM Treasury Consolidated Sanctions List',
            'url': self.UK_CONSOLIDATED_LIST_URL,
            'last_update': self._last_update.isoformat() + 'Z' if self._last_update else None,
            'update_frequency': 'Weekly (typically Thursday)',
            'entity_types': ['Individual', 'Entity', 'Ship', 'Aircraft'],
            'coverage': 'UK financial sanctions and asset freezes',
            'match_types': ['exact', 'fuzzy', 'alias'],
            'regimes': len(self.get_sanctions_regimes()),
            'sanctions_types': ['Asset freeze', 'Travel ban', 'Investment ban', 'Trade restrictions']
        }
    
    def search_by_regime(self, regime_code: str, limit: int = 50) -> Dict[str, Any]:
        """
        Search entities by UK sanctions regime.
        
        Args:
            regime_code: UK sanctions regime code (e.g., 'Russia')
            limit: Maximum number of results
            
        Returns:
            Search results for the regime
        """
        try:
            # In production, this would search the indexed UK sanctions data
            # For demo, return mock results
            
            demo_results = []
            if regime_code == 'Russia':
                demo_results = [
                    {
                        'name': 'SBERBANK OF RUSSIA',
                        'entity_type': 'Entity',
                        'uk_unique_id': 'RUS0001',
                        'listing_date': '2022-02-26',
                        'sanctions_imposed': ['Asset freeze', 'Investment ban'],
                        'aliases': ['SBERBANK', 'SBER']
                    },
                    {
                        'name': 'VLADIMIR VLADIMIROVICH PUTIN',
                        'entity_type': 'Individual',
                        'uk_unique_id': 'RUS0003',
                        'listing_date': '2022-02-25',
                        'sanctions_imposed': ['Asset freeze', 'Travel ban'],
                        'aliases': ['PUTIN', 'VLADIMIR PUTIN']
                    }
                ]
            
            return {
                'regime_code': regime_code,
                'total_results': len(demo_results),
                'results': demo_results[:limit],
                'search_time_ms': 30
            }
            
        except Exception as e:
            logger.error("UK regime search failed", regime=regime_code, error=str(e))
            return {
                'regime_code': regime_code,
                'error': str(e),
                'total_results': 0,
                'results': []
            }
    
    def get_entity_details(self, uk_unique_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific sanctioned entity.
        
        Args:
            uk_unique_id: UK unique identifier for the entity
            
        Returns:
            Detailed entity information
        """
        try:
            # In production, this would query the full entity record
            # For demo, return mock detailed data
            
            if uk_unique_id == 'RUS0001':
                return {
                    'uk_unique_id': 'RUS0001',
                    'name': 'SBERBANK OF RUSSIA',
                    'entity_type': 'Entity',
                    'regime': 'Russia',
                    'listing_date': '2022-02-26',
                    'sanctions_imposed': ['Asset freeze', 'Investment ban'],
                    'aliases': ['SBERBANK', 'SBER', 'SBERBANK ROSSII'],
                    'addresses': [
                        {
                            'address': '19 Vavilova Street, Moscow 117997, Russia',
                            'country': 'Russia'
                        }
                    ],
                    'other_information': 'Major Russian state-owned bank',
                    'last_updated': '2022-02-26'
                }
            
            return {
                'error': f'Entity with ID {uk_unique_id} not found',
                'uk_unique_id': uk_unique_id
            }
            
        except Exception as e:
            logger.error("UK entity details lookup failed", uk_unique_id=uk_unique_id, error=str(e))
            return {
                'uk_unique_id': uk_unique_id,
                'error': str(e)
            }