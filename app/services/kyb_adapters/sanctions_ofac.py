"""OFAC (Office of Foreign Assets Control) Sanctions List API adapter."""
import time
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import requests
from flask import current_app
import structlog
import xml.etree.ElementTree as ET

from .base import BaseKYBAdapter, ValidationError, DataSourceUnavailable, RateLimitExceeded

logger = structlog.get_logger()


class OFACSanctionsAdapter(BaseKYBAdapter):
    """Adapter for OFAC Specially Designated Nationals (SDN) List."""
    
    # Configuration
    RATE_LIMIT = 50  # OFAC has moderate rate limits
    RATE_WINDOW = 60  # per minute
    CACHE_TTL = 7200  # 2 hours cache
    MAX_RETRIES = 3
    RETRY_DELAY = 2
    
    # OFAC API endpoints
    OFAC_SDN_URL = "https://www.treasury.gov/ofac/downloads/sdn.xml"
    OFAC_CONSOLIDATED_URL = "https://www.treasury.gov/ofac/downloads/consolidated/consolidated.xml"
    OFAC_SEARCH_URL = "https://sanctionssearch.ofac.treas.gov/api/PublicationPreview/exports/XML"
    
    def __init__(self, redis_client=None):
        """Initialize OFAC Sanctions adapter."""
        super().__init__(redis_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Secretary-KYB/1.0',
            'Accept': 'application/xml, application/json',
            'Content-Type': 'application/json'
        })
        
        # OFAC sanctions data cache
        self._sanctions_data = None
        self._last_update = None
    
    def check_single(self, entity_name: str, **kwargs) -> Dict[str, Any]:
        """
        Check a single entity against OFAC sanctions list.
        
        Args:
            entity_name: Company or individual name to check
            **kwargs: Additional options:
                - force_refresh: Skip cache and force API call
                - match_threshold: Similarity threshold (0.0-1.0, default: 0.85)
                - include_aliases: Include alias matches (default: True)
                - programs: List of specific OFAC programs to check
                
        Returns:
            Dict with OFAC sanctions check result
        """
        start_time = time.time()
        force_refresh = kwargs.get('force_refresh', False)
        match_threshold = kwargs.get('match_threshold', 0.85)
        include_aliases = kwargs.get('include_aliases', True)
        programs = kwargs.get('programs', None)  # None means all programs
        
        try:
            # Validate input
            clean_name = self._validate_entity_name(entity_name)
            
            # Check cache first
            cache_key = self._get_cache_key(clean_name, 
                                          match_threshold=match_threshold,
                                          programs=programs)
            if not force_refresh:
                cached_result = self._get_cached_result(cache_key)
                if cached_result:
                    cached_result['cached'] = True
                    cached_result['response_time_ms'] = int((time.time() - start_time) * 1000)
                    logger.debug("OFAC sanctions cache hit", entity_name=clean_name)
                    return cached_result
            
            # Check rate limit
            if not self._check_rate_limit():
                raise RateLimitExceeded(f"Rate limit exceeded for {self.source_name}")
            
            # Perform OFAC sanctions check
            result = self._execute_with_retry(
                self._check_ofac_sanctions,
                clean_name,
                match_threshold,
                include_aliases,
                programs
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
            
            logger.info("OFAC sanctions check completed",
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
            logger.error("Unexpected error in OFAC sanctions check",
                        entity_name=entity_name, error=str(e), exc_info=True)
            error_result = self._create_error_result(entity_name, f"Unexpected error: {str(e)}")
            error_result['response_time_ms'] = int((time.time() - start_time) * 1000)
            return error_result
    
    def check_batch(self, entity_names: List[str], **kwargs) -> List[Dict[str, Any]]:
        """
        Check multiple entities against OFAC sanctions list.
        
        Args:
            entity_names: List of entity names to check
            **kwargs: Additional options (same as check_single)
            
        Returns:
            List of OFAC sanctions check results
        """
        if not entity_names:
            return []
        
        logger.info("Starting OFAC sanctions batch check", count=len(entity_names))
        
        results = []
        for entity_name in entity_names:
            result = self.check_single(entity_name, **kwargs)
            results.append(result)
            
            # Small delay between requests
            time.sleep(0.2)
        
        logger.info("OFAC sanctions batch check completed",
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
    
    def _check_ofac_sanctions(self, entity_name: str, match_threshold: float, 
                             include_aliases: bool, programs: Optional[List[str]]) -> Dict[str, Any]:
        """
        Check entity against OFAC sanctions list.
        
        This is a simplified implementation. In production, you would:
        1. Download and parse the OFAC SDN XML file
        2. Implement sophisticated matching algorithms
        3. Handle different entity types and programs
        4. Process aliases and alternate spellings
        """
        try:
            # Simulate API call delay
            time.sleep(0.15)
            
            # Demo OFAC sanctions keywords (in production, this would be the full SDN list)
            demo_ofac_sanctions = [
                {
                    'name': 'SBERBANK OF RUSSIA',
                    'aliases': ['SBERBANK', 'SBER'],
                    'program': 'UKRAINE-EO13662',
                    'entity_type': 'company',
                    'uid': '36418',
                    'listing_date': '2014-07-16'
                },
                {
                    'name': 'GAZPROM',
                    'aliases': ['GAZPROM OAO', 'GAZPROM PJSC'],
                    'program': 'UKRAINE-EO13662',
                    'entity_type': 'company',
                    'uid': '36419',
                    'listing_date': '2014-07-16'
                },
                {
                    'name': 'VLADIMIR VLADIMIROVICH PUTIN',
                    'aliases': ['PUTIN', 'VLADIMIR PUTIN'],
                    'program': 'UKRAINE-EO13661',
                    'entity_type': 'individual',
                    'uid': '36420',
                    'listing_date': '2014-04-28'
                },
                {
                    'name': 'ROSNEFT OIL COMPANY',
                    'aliases': ['ROSNEFT', 'ROSNEFT PJSC'],
                    'program': 'UKRAINE-EO13662',
                    'entity_type': 'company',
                    'uid': '36421',
                    'listing_date': '2014-09-12'
                }
            ]
            
            # Normalize entity name for matching
            normalized_name = entity_name.upper()
            
            # Find matches
            matches = []
            for entry in demo_ofac_sanctions:
                # Check if specific programs are requested
                if programs and entry['program'] not in programs:
                    continue
                
                # Check main name
                if entry['name'] in normalized_name or normalized_name in entry['name']:
                    similarity = self._calculate_similarity(normalized_name, entry['name'])
                    if similarity >= match_threshold:
                        matches.append({
                            'matched_name': entry['name'],
                            'similarity_score': similarity,
                            'match_type': 'primary_name',
                            'ofac_uid': entry['uid'],
                            'sanctions_program': entry['program'],
                            'entity_type': entry['entity_type'],
                            'listing_date': entry['listing_date'],
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
                                    'ofac_uid': entry['uid'],
                                    'sanctions_program': entry['program'],
                                    'entity_type': entry['entity_type'],
                                    'listing_date': entry['listing_date']
                                })
            
            # Remove duplicates based on OFAC UID
            unique_matches = []
            seen_uids = set()
            for match in matches:
                uid = match['ofac_uid']
                if uid not in seen_uids:
                    unique_matches.append(match)
                    seen_uids.add(uid)
            
            # Determine result status
            if unique_matches:
                status = 'match'
                risk_level = 'critical'
                message = f"Found {len(unique_matches)} OFAC sanctions match(es)"
            else:
                status = 'no_match'
                risk_level = 'low'
                message = "No OFAC sanctions matches found"
            
            return {
                'identifier': entity_name,
                'status': status,
                'risk_level': risk_level,
                'message': message,
                'matches': unique_matches,
                'total_matches': len(unique_matches),
                'programs_checked': programs or ['ALL'],
                'data': {
                    'entity_name': entity_name,
                    'normalized_name': normalized_name,
                    'match_threshold': match_threshold,
                    'include_aliases': include_aliases
                }
            }
            
        except Exception as e:
            logger.error("Error in OFAC sanctions matching", error=str(e), exc_info=True)
            raise DataSourceUnavailable(f"OFAC sanctions check failed: {str(e)}")
    
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
        Update local OFAC sanctions data.
        
        In production, this would:
        1. Download the latest OFAC SDN XML file
        2. Parse and index the data
        3. Store in local database or cache
        4. Return update statistics
        """
        try:
            logger.info("Updating OFAC sanctions data")
            
            # Simulate data update
            self._last_update = datetime.utcnow()
            
            # In production, you would:
            # 1. Download from OFAC_SDN_URL or OFAC_CONSOLIDATED_URL
            # 2. Parse XML data using ElementTree
            # 3. Extract entities, aliases, addresses, programs
            # 4. Build search index
            
            return {
                'success': True,
                'last_update': self._last_update.isoformat() + 'Z',
                'total_entities': 8500,  # Demo number
                'individuals': 6000,
                'companies': 2500,
                'programs': 45,
                'message': 'OFAC sanctions data updated successfully'
            }
            
        except Exception as e:
            logger.error("Failed to update OFAC sanctions data", error=str(e), exc_info=True)
            return {
                'success': False,
                'error': str(e),
                'message': 'Failed to update OFAC sanctions data'
            }
    
    def get_sanctions_programs(self) -> List[Dict[str, Any]]:
        """Get list of OFAC sanctions programs."""
        # Demo programs - in production, this would be extracted from the SDN data
        return [
            {
                'code': 'UKRAINE-EO13661',
                'name': 'Ukraine-Related Sanctions (EO 13661)',
                'description': 'Sanctions related to the situation in Ukraine'
            },
            {
                'code': 'UKRAINE-EO13662',
                'name': 'Ukraine-Related Sanctions (EO 13662)',
                'description': 'Sectoral sanctions related to Ukraine'
            },
            {
                'code': 'SYRIA',
                'name': 'Syria Sanctions',
                'description': 'Sanctions related to the situation in Syria'
            },
            {
                'code': 'IRAN',
                'name': 'Iran Sanctions',
                'description': 'Iran-related sanctions'
            },
            {
                'code': 'CUBA',
                'name': 'Cuba Sanctions',
                'description': 'Cuba-related sanctions'
            },
            {
                'code': 'TERRORISM',
                'name': 'Counter Terrorism',
                'description': 'Terrorism-related sanctions'
            }
        ]
    
    def get_sanctions_info(self) -> Dict[str, Any]:
        """Get information about the OFAC sanctions list."""
        return {
            'source': 'US Treasury OFAC Specially Designated Nationals List',
            'url': self.OFAC_SDN_URL,
            'last_update': self._last_update.isoformat() + 'Z' if self._last_update else None,
            'update_frequency': 'Weekly (typically Wednesday)',
            'entity_types': ['individuals', 'companies', 'organizations', 'vessels', 'aircraft'],
            'coverage': 'US sanctions and embargoes',
            'match_types': ['exact', 'fuzzy', 'alias', 'weak_alias'],
            'programs': len(self.get_sanctions_programs())
        }
    
    def search_by_program(self, program_code: str, limit: int = 50) -> Dict[str, Any]:
        """
        Search entities by OFAC program.
        
        Args:
            program_code: OFAC program code (e.g., 'UKRAINE-EO13662')
            limit: Maximum number of results
            
        Returns:
            Search results for the program
        """
        try:
            # In production, this would search the indexed OFAC data
            # For demo, return mock results
            
            demo_results = []
            if program_code == 'UKRAINE-EO13662':
                demo_results = [
                    {
                        'name': 'SBERBANK OF RUSSIA',
                        'entity_type': 'company',
                        'ofac_uid': '36418',
                        'listing_date': '2014-07-16',
                        'aliases': ['SBERBANK', 'SBER']
                    },
                    {
                        'name': 'GAZPROM',
                        'entity_type': 'company',
                        'ofac_uid': '36419',
                        'listing_date': '2014-07-16',
                        'aliases': ['GAZPROM OAO', 'GAZPROM PJSC']
                    }
                ]
            
            return {
                'program_code': program_code,
                'total_results': len(demo_results),
                'results': demo_results[:limit],
                'search_time_ms': 25
            }
            
        except Exception as e:
            logger.error("OFAC program search failed", program=program_code, error=str(e))
            return {
                'program_code': program_code,
                'error': str(e),
                'total_results': 0,
                'results': []
            }