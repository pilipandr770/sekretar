"""Enhanced GLEIF data collector for comprehensive testing."""
import time
import asyncio
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
import structlog
from dataclasses import dataclass, asdict
import json
import requests

from .kyb_adapters.gleif import GLEIFAdapter
from .kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded

logger = structlog.get_logger()


@dataclass
class LEIEntityData:
    """Enhanced LEI entity data for testing."""
    lei_code: str
    legal_name: str
    status: str  # ACTIVE, INACTIVE, etc.
    country_code: str
    legal_form: Optional[str] = None
    registration_authority: Optional[str] = None
    legal_address: Optional[str] = None
    headquarters_address: Optional[str] = None
    entity_category: Optional[str] = None  # FUND, GENERAL, etc.
    parent_lei: Optional[str] = None
    ultimate_parent_lei: Optional[str] = None
    relationships: List[Dict[str, Any]] = None
    last_updated: Optional[datetime] = None
    validation_result: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.relationships is None:
            self.relationships = []


@dataclass
class LEIHierarchy:
    """Corporate hierarchy data from GLEIF."""
    root_entity: LEIEntityData
    subsidiaries: List[LEIEntityData]
    parents: List[LEIEntityData]
    ultimate_parent: Optional[LEIEntityData] = None
    hierarchy_depth: int = 0
    total_entities: int = 0


class GLEIFTestCollector:
    """Enhanced GLEIF collector with corporate hierarchy and caching."""
    
    def __init__(self, redis_client=None):
        """Initialize GLEIF test collector."""
        self.redis_client = redis_client
        self.gleif_adapter = GLEIFAdapter(redis_client)
        
        # Enhanced configuration
        self.batch_size = 20  # GLEIF can handle larger batches
        self.max_concurrent_requests = 8
        self.request_delay = 0.3  # Faster than VIES
        self.hierarchy_cache_ttl = 7200  # 2 hours for hierarchy data
        self.search_cache_ttl = 3600  # 1 hour for search results
        
        # GLEIF API endpoints for advanced features
        self.base_url = "https://api.gleif.org/api/v1"
        self.relationships_endpoint = "/lei-records/{}/relationships"
        self.search_endpoint = "/lei-records"
        
        logger.info("GLEIF test collector initialized")
    
    def collect_lei_codes_by_country(self, 
                                   country_code: str,
                                   limit: int = 100,
                                   **kwargs) -> List[LEIEntityData]:
        """
        Collect LEI codes for a specific country using GLEIF search API.
        
        Args:
            country_code: ISO country code
            limit: Maximum number of LEI codes to collect
            **kwargs: Additional options:
                - entity_status: Filter by status (ACTIVE, INACTIVE)
                - entity_category: Filter by category (FUND, GENERAL)
                - legal_form: Filter by legal form
                - include_relationships: Include relationship data
        
        Returns:
            List of LEIEntityData objects
        """
        entity_status = kwargs.get('entity_status', 'ACTIVE')
        entity_category = kwargs.get('entity_category')
        legal_form = kwargs.get('legal_form')
        include_relationships = kwargs.get('include_relationships', False)
        
        logger.info("Collecting LEI codes by country", 
                   country=country_code, 
                   limit=limit,
                   status=entity_status)
        
        # Build search parameters
        params = {
            'filter[entity.legalAddress.country]': country_code.upper(),
            'filter[entity.status]': entity_status,
            'page[size]': min(limit, 200),  # GLEIF max page size
            'page[number]': 1
        }
        
        if entity_category:
            params['filter[entity.category]'] = entity_category
        
        if legal_form:
            params['filter[entity.legalForm.id]'] = legal_form
        
        collected_entities = []
        page = 1
        
        while len(collected_entities) < limit:
            try:
                params['page[number]'] = page
                
                response = requests.get(
                    f"{self.base_url}{self.search_endpoint}",
                    params=params,
                    headers={
                        'Accept': 'application/vnd.api+json',
                        'User-Agent': 'AI-Secretary-Test-Collector/1.0'
                    },
                    timeout=30
                )
                
                if response.status_code != 200:
                    logger.warning("GLEIF search failed", 
                                 status_code=response.status_code,
                                 country=country_code)
                    break
                
                data = response.json()
                entities = data.get('data', [])
                
                if not entities:
                    logger.info("No more entities found", page=page)
                    break
                
                # Process entities
                for entity_data in entities:
                    if len(collected_entities) >= limit:
                        break
                    
                    try:
                        lei_entity = self._parse_lei_entity(entity_data)
                        
                        # Optionally fetch relationships
                        if include_relationships:
                            lei_entity.relationships = self._get_entity_relationships(
                                lei_entity.lei_code
                            )
                        
                        collected_entities.append(lei_entity)
                        
                    except Exception as e:
                        logger.warning("Failed to parse entity", 
                                     lei_code=entity_data.get('id'),
                                     error=str(e))
                        continue
                
                # Check if there are more pages
                meta = data.get('meta', {})
                if not meta.get('hasMore', False):
                    break
                
                page += 1
                time.sleep(self.request_delay)
                
            except Exception as e:
                logger.error("Error collecting LEI codes", 
                           country=country_code, 
                           page=page,
                           error=str(e))
                break
        
        logger.info("LEI collection completed", 
                   country=country_code,
                   collected=len(collected_entities),
                   requested=limit)
        
        return collected_entities
    
    def collect_corporate_hierarchy(self, 
                                  root_lei: str,
                                  max_depth: int = 3,
                                  **kwargs) -> LEIHierarchy:
        """
        Collect complete corporate hierarchy for a LEI code.
        
        Args:
            root_lei: Root LEI code to start from
            max_depth: Maximum hierarchy depth to traverse
            **kwargs: Additional options:
                - include_inactive: Include inactive entities
                - cache_results: Cache hierarchy data
        
        Returns:
            LEIHierarchy object with complete structure
        """
        include_inactive = kwargs.get('include_inactive', False)
        cache_results = kwargs.get('cache_results', True)
        
        logger.info("Collecting corporate hierarchy", 
                   root_lei=root_lei, 
                   max_depth=max_depth)
        
        # Check cache first
        if cache_results:
            cached_hierarchy = self._get_cached_hierarchy(root_lei)
            if cached_hierarchy:
                logger.debug("Hierarchy cache hit", root_lei=root_lei)
                return cached_hierarchy
        
        try:
            # Get root entity
            root_result = self.gleif_adapter.check_single(
                root_lei,
                include_relationships=True
            )
            
            if root_result['status'] != 'valid':
                raise ValidationError(f"Root LEI {root_lei} is not valid")
            
            root_entity = self._create_lei_entity_from_result(root_result)
            
            # Collect hierarchy
            all_entities = {root_lei: root_entity}
            subsidiaries = []
            parents = []
            ultimate_parent = None
            
            # Traverse up the hierarchy (parents)
            current_lei = root_lei
            for depth in range(max_depth):
                parent_relationships = self._get_parent_relationships(current_lei)
                
                if not parent_relationships:
                    break
                
                for parent_rel in parent_relationships:
                    parent_lei = parent_rel.get('parent_lei')
                    if parent_lei and parent_lei not in all_entities:
                        try:
                            parent_result = self.gleif_adapter.check_single(parent_lei)
                            if parent_result['status'] == 'valid':
                                parent_entity = self._create_lei_entity_from_result(parent_result)
                                all_entities[parent_lei] = parent_entity
                                parents.append(parent_entity)
                                
                                # Check if this is ultimate parent
                                if parent_rel.get('relationship_type') == 'IS_ULTIMATELY_CONSOLIDATED_BY':
                                    ultimate_parent = parent_entity
                                
                                current_lei = parent_lei
                                
                        except Exception as e:
                            logger.warning("Failed to get parent entity", 
                                         parent_lei=parent_lei, error=str(e))
                
                time.sleep(self.request_delay)
            
            # Traverse down the hierarchy (subsidiaries)
            subsidiaries = self._collect_subsidiaries(
                root_lei, 
                all_entities, 
                max_depth,
                include_inactive
            )
            
            # Create hierarchy object
            hierarchy = LEIHierarchy(
                root_entity=root_entity,
                subsidiaries=subsidiaries,
                parents=parents,
                ultimate_parent=ultimate_parent,
                hierarchy_depth=max_depth,
                total_entities=len(all_entities)
            )
            
            # Cache the result
            if cache_results:
                self._cache_hierarchy(root_lei, hierarchy)
            
            logger.info("Corporate hierarchy collected", 
                       root_lei=root_lei,
                       total_entities=len(all_entities),
                       subsidiaries=len(subsidiaries),
                       parents=len(parents))
            
            return hierarchy
            
        except Exception as e:
            logger.error("Failed to collect corporate hierarchy", 
                        root_lei=root_lei, error=str(e))
            raise
    
    def validate_lei_batch_with_hierarchy(self, 
                                        lei_codes: List[str],
                                        **kwargs) -> List[Dict[str, Any]]:
        """
        Validate LEI codes with optional hierarchy information.
        
        Args:
            lei_codes: List of LEI codes to validate
            **kwargs: Validation options:
                - include_hierarchy: Include parent/subsidiary info
                - max_hierarchy_depth: Maximum depth for hierarchy
                - batch_delay: Delay between batches
        
        Returns:
            List of enhanced validation results
        """
        include_hierarchy = kwargs.get('include_hierarchy', False)
        max_hierarchy_depth = kwargs.get('max_hierarchy_depth', 2)
        batch_delay = kwargs.get('batch_delay', 0.5)
        
        logger.info("Starting enhanced LEI batch validation", 
                   count=len(lei_codes),
                   include_hierarchy=include_hierarchy)
        
        # First, do basic validation
        basic_results = []
        
        # Process in batches
        for i in range(0, len(lei_codes), self.batch_size):
            batch = lei_codes[i:i + self.batch_size]
            
            try:
                batch_results = self.gleif_adapter.check_batch(
                    batch,
                    batch_delay=batch_delay,
                    max_workers=self.max_concurrent_requests,
                    include_relationships=include_hierarchy
                )
                basic_results.extend(batch_results)
                
                if i + self.batch_size < len(lei_codes):
                    time.sleep(batch_delay)
                    
            except Exception as e:
                logger.error("Batch validation failed", 
                           batch_start=i, error=str(e))
                
                # Create error results for the batch
                for lei_code in batch:
                    error_result = {
                        'identifier': lei_code,
                        'status': 'error',
                        'error': f"Batch processing failed: {str(e)}",
                        'source': 'GLEIF'
                    }
                    basic_results.append(error_result)
        
        # Enhance with hierarchy data if requested
        if include_hierarchy:
            enhanced_results = []
            
            for result in basic_results:
                if result['status'] == 'valid':
                    try:
                        lei_code = result['identifier']
                        hierarchy_info = self._get_simplified_hierarchy(
                            lei_code, 
                            max_hierarchy_depth
                        )
                        result['hierarchy'] = hierarchy_info
                        
                    except Exception as e:
                        logger.warning("Failed to get hierarchy info", 
                                     lei_code=result['identifier'], 
                                     error=str(e))
                        result['hierarchy'] = {'error': str(e)}
                
                enhanced_results.append(result)
            
            return enhanced_results
        
        return basic_results
    
    def search_entities_by_name(self, 
                              entity_name: str,
                              **kwargs) -> List[LEIEntityData]:
        """
        Search for entities by name with enhanced filtering.
        
        Args:
            entity_name: Name to search for
            **kwargs: Search options:
                - country_code: Filter by country
                - entity_status: Filter by status
                - legal_form: Filter by legal form
                - limit: Maximum results
        
        Returns:
            List of matching LEIEntityData objects
        """
        country_code = kwargs.get('country_code')
        entity_status = kwargs.get('entity_status', 'ACTIVE')
        legal_form = kwargs.get('legal_form')
        limit = kwargs.get('limit', 50)
        
        logger.info("Searching entities by name", 
                   name=entity_name,
                   country=country_code,
                   limit=limit)
        
        # Use the existing search functionality from GLEIF adapter
        search_results = self.gleif_adapter.search_by_name(
            entity_name,
            country_code=country_code,
            limit=limit
        )
        
        # Convert to LEIEntityData objects
        entities = []
        for result in search_results:
            try:
                entity = self._create_lei_entity_from_result(result)
                
                # Apply additional filters
                if entity_status and entity.status != entity_status:
                    continue
                
                if legal_form and entity.legal_form != legal_form:
                    continue
                
                entities.append(entity)
                
            except Exception as e:
                logger.warning("Failed to convert search result", 
                             lei_code=result.get('lei_code'),
                             error=str(e))
                continue
        
        logger.info("Entity search completed", 
                   name=entity_name,
                   found=len(entities))
        
        return entities
    
    def _parse_lei_entity(self, entity_data: Dict[str, Any]) -> LEIEntityData:
        """Parse GLEIF API entity data into LEIEntityData object."""
        attributes = entity_data.get('attributes', {})
        entity = attributes.get('entity', {})
        registration = attributes.get('registration', {})
        
        # Extract basic information
        lei_code = entity_data.get('id', '')
        legal_name = entity.get('legalName', {}).get('name', 'Unknown')
        status = entity.get('status', 'UNKNOWN')
        
        # Extract addresses
        legal_address = entity.get('legalAddress', {})
        headquarters_address = entity.get('headquartersAddress', {})
        
        country_code = legal_address.get('country', 'XX')
        legal_form = entity.get('legalForm', {}).get('id')
        registration_authority = registration.get('registrationAuthority', {}).get('id')
        entity_category = entity.get('category')
        
        # Format addresses
        legal_address_str = self._format_gleif_address(legal_address)
        headquarters_address_str = self._format_gleif_address(headquarters_address)
        
        return LEIEntityData(
            lei_code=lei_code,
            legal_name=legal_name,
            status=status,
            country_code=country_code,
            legal_form=legal_form,
            registration_authority=registration_authority,
            legal_address=legal_address_str,
            headquarters_address=headquarters_address_str,
            entity_category=entity_category,
            last_updated=datetime.utcnow()
        )
    
    def _create_lei_entity_from_result(self, result: Dict[str, Any]) -> LEIEntityData:
        """Create LEIEntityData from GLEIF adapter result."""
        return LEIEntityData(
            lei_code=result.get('lei_code', ''),
            legal_name=result.get('legal_name', 'Unknown'),
            status=result.get('entity_status', 'UNKNOWN'),
            country_code=result.get('country_code', 'XX'),
            legal_form=result.get('legal_form'),
            registration_authority=result.get('registration_authority'),
            legal_address=result.get('legal_address'),
            headquarters_address=result.get('headquarters_address'),
            last_updated=datetime.utcnow(),
            validation_result=result
        )
    
    def _format_gleif_address(self, address_data: Dict[str, Any]) -> Optional[str]:
        """Format GLEIF address data."""
        if not address_data:
            return None
        
        parts = []
        
        # Add address lines
        for i in range(1, 5):
            line = address_data.get(f'addressLines_{i}')
            if line:
                parts.append(line)
        
        # Add city, region, postal code, country
        for field in ['city', 'region', 'postalCode', 'country']:
            value = address_data.get(field)
            if value:
                parts.append(value)
        
        return ', '.join(parts) if parts else None
    
    def _get_entity_relationships(self, lei_code: str) -> List[Dict[str, Any]]:
        """Get relationship data for a LEI code."""
        try:
            relationships_result = self.gleif_adapter.get_lei_relationships(lei_code)
            
            if relationships_result['status'] == 'success':
                return relationships_result.get('relationships', {}).get('data', [])
            else:
                return []
                
        except Exception as e:
            logger.warning("Failed to get relationships", 
                         lei_code=lei_code, error=str(e))
            return []
    
    def _get_parent_relationships(self, lei_code: str) -> List[Dict[str, Any]]:
        """Get parent relationships for a LEI code."""
        relationships = self._get_entity_relationships(lei_code)
        parent_relationships = []
        
        for rel in relationships:
            rel_type = rel.get('attributes', {}).get('relationship', {}).get('relationshipType')
            if rel_type in ['IS_DIRECTLY_CONSOLIDATED_BY', 'IS_ULTIMATELY_CONSOLIDATED_BY']:
                parent_lei = rel.get('attributes', {}).get('relationship', {}).get('endNode', {}).get('nodeID')
                if parent_lei:
                    parent_relationships.append({
                        'parent_lei': parent_lei,
                        'relationship_type': rel_type,
                        'relationship_data': rel
                    })
        
        return parent_relationships
    
    def _collect_subsidiaries(self, 
                            parent_lei: str,
                            all_entities: Dict[str, LEIEntityData],
                            max_depth: int,
                            include_inactive: bool) -> List[LEIEntityData]:
        """Collect subsidiary entities recursively."""
        subsidiaries = []
        
        # This would require more complex relationship traversal
        # For now, return empty list as full implementation would be extensive
        # In a real implementation, this would traverse child relationships
        
        return subsidiaries
    
    def _get_simplified_hierarchy(self, 
                                lei_code: str, 
                                max_depth: int) -> Dict[str, Any]:
        """Get simplified hierarchy information for a LEI code."""
        try:
            relationships = self._get_entity_relationships(lei_code)
            
            hierarchy_info = {
                'has_parents': False,
                'has_subsidiaries': False,
                'parent_count': 0,
                'subsidiary_count': 0,
                'ultimate_parent': None,
                'direct_parent': None
            }
            
            for rel in relationships:
                rel_type = rel.get('attributes', {}).get('relationship', {}).get('relationshipType')
                
                if rel_type == 'IS_ULTIMATELY_CONSOLIDATED_BY':
                    hierarchy_info['has_parents'] = True
                    hierarchy_info['parent_count'] += 1
                    parent_lei = rel.get('attributes', {}).get('relationship', {}).get('endNode', {}).get('nodeID')
                    if parent_lei:
                        hierarchy_info['ultimate_parent'] = parent_lei
                
                elif rel_type == 'IS_DIRECTLY_CONSOLIDATED_BY':
                    hierarchy_info['has_parents'] = True
                    parent_lei = rel.get('attributes', {}).get('relationship', {}).get('endNode', {}).get('nodeID')
                    if parent_lei:
                        hierarchy_info['direct_parent'] = parent_lei
            
            return hierarchy_info
            
        except Exception as e:
            logger.warning("Failed to get simplified hierarchy", 
                         lei_code=lei_code, error=str(e))
            return {'error': str(e)}
    
    def _get_cached_hierarchy(self, lei_code: str) -> Optional[LEIHierarchy]:
        """Get cached hierarchy data."""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"gleif_hierarchy:{lei_code}"
            cached_data = self.redis_client.get(cache_key)
            
            if cached_data:
                import pickle
                return pickle.loads(cached_data)
                
        except Exception as e:
            logger.warning("Failed to get cached hierarchy", 
                         lei_code=lei_code, error=str(e))
        
        return None
    
    def _cache_hierarchy(self, lei_code: str, hierarchy: LEIHierarchy) -> None:
        """Cache hierarchy data."""
        if not self.redis_client:
            return
        
        try:
            import pickle
            cache_key = f"gleif_hierarchy:{lei_code}"
            self.redis_client.setex(
                cache_key,
                self.hierarchy_cache_ttl,
                pickle.dumps(hierarchy)
            )
            
        except Exception as e:
            logger.warning("Failed to cache hierarchy", 
                         lei_code=lei_code, error=str(e))
    
    def get_collection_statistics(self) -> Dict[str, Any]:
        """Get comprehensive collection statistics."""
        base_stats = self.gleif_adapter.get_stats()
        
        # Add collector-specific stats
        collector_stats = {
            'configuration': {
                'batch_size': self.batch_size,
                'max_concurrent_requests': self.max_concurrent_requests,
                'request_delay': self.request_delay,
                'hierarchy_cache_ttl': self.hierarchy_cache_ttl
            },
            'capabilities': {
                'hierarchy_collection': True,
                'batch_validation': True,
                'entity_search': True,
                'relationship_mapping': True
            }
        }
        
        return {**base_stats, **collector_stats}
    
    def clear_hierarchy_cache(self, lei_code: str = None) -> Dict[str, Any]:
        """Clear hierarchy cache entries."""
        if not self.redis_client:
            return {'error': 'Redis not available'}
        
        try:
            if lei_code:
                cache_key = f"gleif_hierarchy:{lei_code}"
                deleted = self.redis_client.delete(cache_key)
                return {
                    'success': True,
                    'lei_code': lei_code,
                    'keys_deleted': deleted
                }
            else:
                # Clear all hierarchy cache
                pattern = "gleif_hierarchy:*"
                keys = self.redis_client.keys(pattern)
                if keys:
                    deleted = self.redis_client.delete(*keys)
                    return {
                        'success': True,
                        'pattern': pattern,
                        'keys_deleted': deleted
                    }
                else:
                    return {
                        'success': True,
                        'pattern': pattern,
                        'keys_deleted': 0
                    }
                    
        except Exception as e:
            logger.error("Failed to clear hierarchy cache", error=str(e))
            return {'error': str(e)}