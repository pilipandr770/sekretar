"""
Test Data Manager

Manages real company data collection and validation for comprehensive testing.
"""
import asyncio
import logging
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Set
import httpx
import xml.etree.ElementTree as ET
from dataclasses import asdict

from tests.infrastructure.models import CompanyData, DataSourceConfig


class TestDataManager:
    """
    Manages collection and validation of real company data for testing.
    
    Collects data from public sources like VIES, GLEIF, Companies House, etc.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize test data manager."""
        self.config = config
        self.logger = logging.getLogger(__name__)
        
        # Data source configuration
        self.data_source_config = DataSourceConfig(
            vies_api_url=config.get('vies_api_url', 'https://ec.europa.eu/taxation_customs/vies/services/checkVatService'),
            gleif_api_url=config.get('gleif_api_url', 'https://api.gleif.org/api/v1'),
            companies_house_api_key=config.get('companies_house_api_key'),
            opencorporates_api_key=config.get('opencorporates_api_key'),
            rate_limits=config.get('rate_limits', {
                'vies': 10,  # requests per minute
                'gleif': 60,
                'companies_house': 600,
                'opencorporates': 500
            }),
            timeout_seconds=config.get('timeout_seconds', 30),
            retry_attempts=config.get('retry_attempts', 3)
        )
        
        # Cache for collected data
        self.company_data_cache: Dict[str, CompanyData] = {}
        self.last_cache_update: Optional[datetime] = None
        
        # Rate limiting tracking
        self.rate_limit_trackers: Dict[str, List[datetime]] = {
            'vies': [],
            'gleif': [],
            'companies_house': [],
            'opencorporates': []
        }
        
        # HTTP client
        self.http_client: Optional[httpx.AsyncClient] = None
    
    async def initialize(self):
        """Initialize test data manager."""
        self.logger.info("Initializing test data manager")
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(
            timeout=self.data_source_config.timeout_seconds,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )
        
        # Load cached data if available
        await self._load_cached_data()
        
        self.logger.info("Test data manager initialized")
    
    async def collect_real_company_data(self) -> Dict[str, CompanyData]:
        """
        Collect real company data from various public sources.
        
        Returns:
            Dict[str, CompanyData]: Dictionary of company data keyed by identifier
        """
        self.logger.info("Collecting real company data from public sources")
        
        collected_data = {}
        
        # Collect from predefined list of known companies
        predefined_companies = await self._get_predefined_companies()
        
        for company_id, company_info in predefined_companies.items():
            try:
                company_data = await self._collect_company_data(company_info)
                if company_data:
                    collected_data[company_id] = company_data
                    
                # Respect rate limits
                await self._respect_rate_limits()
                
            except Exception as e:
                self.logger.error(f"Failed to collect data for {company_id}: {str(e)}")
                continue
        
        # Cache collected data
        self.company_data_cache.update(collected_data)
        self.last_cache_update = datetime.utcnow()
        await self._save_cached_data()
        
        self.logger.info(f"Collected data for {len(collected_data)} companies")
        return collected_data
    
    async def _get_predefined_companies(self) -> Dict[str, Dict[str, Any]]:
        """Get predefined list of companies for testing."""
        return {
            "microsoft_ireland": {
                "name": "Microsoft Ireland Operations Limited",
                "vat_number": "IE9825613N",
                "country": "IE",
                "lei_code": "635400AKJKKLMN4KNZ71",
                "address": "One Microsoft Place, South County Business Park, Leopardstown, Dublin 18",
                "industry": "Technology",
                "size": "Large"
            },
            "sap_germany": {
                "name": "SAP SE",
                "vat_number": "DE143593636",
                "country": "DE",
                "lei_code": "529900T8BM49AURSDO55",
                "address": "Dietmar-Hopp-Allee 16, 69190 Walldorf",
                "industry": "Technology",
                "size": "Large"
            },
            "unilever_uk": {
                "name": "Unilever PLC",
                "vat_number": "GB440861235",
                "country": "GB",
                "lei_code": "549300BFXFJ6KBNTKY86",
                "address": "100 Victoria Embankment, London EC4Y 0DY",
                "industry": "Consumer Goods",
                "size": "Large"
            },
            "ing_netherlands": {
                "name": "ING Groep N.V.",
                "vat_number": "NL002491986B04",
                "country": "NL",
                "lei_code": "7245009UXRIGIRYOBR48",
                "address": "Bijlmerplein 888, 1102 MG Amsterdam",
                "industry": "Financial Services",
                "size": "Large"
            },
            "nokia_finland": {
                "name": "Nokia Corporation",
                "vat_number": "FI09140687",
                "country": "FI",
                "lei_code": "549300A0K1JP5A9QXU27",
                "address": "Karaportti 3, 02610 Espoo",
                "industry": "Technology",
                "size": "Large"
            },
            "spotify_sweden": {
                "name": "Spotify AB",
                "vat_number": "SE556703748501",
                "country": "SE",
                "lei_code": "549300BFXFJ6KBNTKY86",  # Note: This is placeholder, actual LEI may differ
                "address": "Regeringsgatan 19, 111 53 Stockholm",
                "industry": "Technology",
                "size": "Large"
            },
            "lvmh_france": {
                "name": "LVMH Moët Hennessy Louis Vuitton SE",
                "vat_number": "FR40775670417",
                "country": "FR",
                "lei_code": "969500FP4DHPD833NQ28",
                "address": "22 Avenue Montaigne, 75008 Paris",
                "industry": "Luxury Goods",
                "size": "Large"
            },
            "bayer_germany": {
                "name": "Bayer AG",
                "vat_number": "DE119850003",
                "country": "DE",
                "lei_code": "54930056FHWP7GIWYY08",
                "address": "Kaiser-Wilhelm-Allee 1, 51373 Leverkusen",
                "industry": "Pharmaceuticals",
                "size": "Large"
            }
        }
    
    async def _collect_company_data(self, company_info: Dict[str, Any]) -> Optional[CompanyData]:
        """Collect and validate data for a specific company."""
        company_data = CompanyData(
            name=company_info['name'],
            vat_number=company_info.get('vat_number'),
            lei_code=company_info.get('lei_code'),
            country_code=company_info['country'],
            address=company_info.get('address'),
            industry=company_info.get('industry'),
            size=company_info.get('size'),
            source='predefined',
            validation_status='PENDING',
            additional_data={}
        )
        
        # Validate VAT number if available
        if company_data.vat_number:
            vat_valid = await self._validate_vat_number(
                company_data.vat_number, 
                company_data.country_code
            )
            company_data.additional_data['vat_validation'] = vat_valid
        
        # Validate LEI code if available
        if company_data.lei_code:
            lei_data = await self._validate_lei_code(company_data.lei_code)
            company_data.additional_data['lei_validation'] = lei_data
        
        # Determine overall validation status
        company_data.validation_status = self._determine_validation_status(company_data)
        company_data.last_validated = datetime.utcnow()
        
        return company_data
    
    async def _validate_vat_number(self, vat_number: str, country_code: str) -> Dict[str, Any]:
        """Validate VAT number using VIES service."""
        try:
            await self._check_rate_limit('vies')
            
            # Prepare SOAP request for VIES
            soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:tns1="urn:ec.europa.eu:taxud:vies:services:checkVat:types">
    <soap:Header>
    </soap:Header>
    <soap:Body>
        <tns1:checkVat>
            <tns1:countryCode>{country_code}</tns1:countryCode>
            <tns1:vatNumber>{vat_number.replace(country_code, '')}</tns1:vatNumber>
        </tns1:checkVat>
    </soap:Body>
</soap:Envelope>"""
            
            headers = {
                'Content-Type': 'text/xml; charset=utf-8',
                'SOAPAction': 'urn:ec.europa.eu:taxud:vies:services:checkVat/checkVat'
            }
            
            response = await self.http_client.post(
                self.data_source_config.vies_api_url,
                content=soap_body,
                headers=headers
            )
            
            if response.status_code == 200:
                # Parse SOAP response
                root = ET.fromstring(response.content)
                
                # Find the checkVatResponse element
                ns = {'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
                      'tns1': 'urn:ec.europa.eu:taxud:vies:services:checkVat:types'}
                
                vat_response = root.find('.//tns1:checkVatResponse', ns)
                if vat_response is not None:
                    valid = vat_response.find('tns1:valid', ns)
                    name = vat_response.find('tns1:name', ns)
                    address = vat_response.find('tns1:address', ns)
                    
                    return {
                        'valid': valid.text.lower() == 'true' if valid is not None else False,
                        'name': name.text if name is not None else None,
                        'address': address.text if address is not None else None,
                        'validated_at': datetime.utcnow().isoformat(),
                        'source': 'vies'
                    }
            
            return {
                'valid': False,
                'error': f'VIES validation failed with status {response.status_code}',
                'validated_at': datetime.utcnow().isoformat(),
                'source': 'vies'
            }
            
        except Exception as e:
            self.logger.error(f"VAT validation failed for {vat_number}: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'validated_at': datetime.utcnow().isoformat(),
                'source': 'vies'
            }
    
    async def _validate_lei_code(self, lei_code: str) -> Dict[str, Any]:
        """Validate LEI code using GLEIF API."""
        try:
            await self._check_rate_limit('gleif')
            
            url = f"{self.data_source_config.gleif_api_url}/lei-records/{lei_code}"
            
            response = await self.http_client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                lei_record = data.get('data', {})
                attributes = lei_record.get('attributes', {})
                
                return {
                    'valid': True,
                    'legal_name': attributes.get('entity', {}).get('legalName', {}).get('name'),
                    'status': attributes.get('entity', {}).get('status'),
                    'registration_authority': attributes.get('registration', {}).get('registrationAuthority', {}).get('registrationAuthorityEntityID'),
                    'jurisdiction': attributes.get('entity', {}).get('legalJurisdiction'),
                    'validated_at': datetime.utcnow().isoformat(),
                    'source': 'gleif'
                }
            elif response.status_code == 404:
                return {
                    'valid': False,
                    'error': 'LEI code not found',
                    'validated_at': datetime.utcnow().isoformat(),
                    'source': 'gleif'
                }
            else:
                return {
                    'valid': False,
                    'error': f'GLEIF validation failed with status {response.status_code}',
                    'validated_at': datetime.utcnow().isoformat(),
                    'source': 'gleif'
                }
                
        except Exception as e:
            self.logger.error(f"LEI validation failed for {lei_code}: {str(e)}")
            return {
                'valid': False,
                'error': str(e),
                'validated_at': datetime.utcnow().isoformat(),
                'source': 'gleif'
            }
    
    def _determine_validation_status(self, company_data: CompanyData) -> str:
        """Determine overall validation status for company data."""
        vat_validation = company_data.additional_data.get('vat_validation', {})
        lei_validation = company_data.additional_data.get('lei_validation', {})
        
        # If we have validations and they're all valid
        validations = []
        if vat_validation:
            validations.append(vat_validation.get('valid', False))
        if lei_validation:
            validations.append(lei_validation.get('valid', False))
        
        if validations:
            if all(validations):
                return 'VALID'
            elif any(validations):
                return 'PARTIALLY_VALID'
            else:
                return 'INVALID'
        else:
            return 'NO_VALIDATION'
    
    async def _check_rate_limit(self, service: str):
        """Check and enforce rate limits for external services."""
        now = datetime.utcnow()
        rate_limit = self.data_source_config.rate_limits.get(service, 60)
        
        # Clean old requests (older than 1 minute)
        self.rate_limit_trackers[service] = [
            req_time for req_time in self.rate_limit_trackers[service]
            if now - req_time < timedelta(minutes=1)
        ]
        
        # Check if we're at the rate limit
        if len(self.rate_limit_trackers[service]) >= rate_limit:
            # Calculate wait time
            oldest_request = min(self.rate_limit_trackers[service])
            wait_time = 60 - (now - oldest_request).total_seconds()
            
            if wait_time > 0:
                self.logger.info(f"Rate limit reached for {service}, waiting {wait_time:.1f} seconds")
                await asyncio.sleep(wait_time)
        
        # Record this request
        self.rate_limit_trackers[service].append(now)
    
    async def _respect_rate_limits(self):
        """Add delay between requests to respect rate limits."""
        await asyncio.sleep(0.5)  # 500ms delay between requests
    
    async def validate_company_data(self, company_data: Dict[str, CompanyData]) -> Dict[str, CompanyData]:
        """Validate collected company data."""
        self.logger.info(f"Validating {len(company_data)} company records")
        
        validated_data = {}
        
        for company_id, data in company_data.items():
            try:
                # Additional validation logic can be added here
                # For now, we'll just ensure required fields are present
                
                if self._is_company_data_valid(data):
                    validated_data[company_id] = data
                else:
                    self.logger.warning(f"Company data validation failed for {company_id}")
                    
            except Exception as e:
                self.logger.error(f"Error validating company data for {company_id}: {str(e)}")
        
        self.logger.info(f"Validated {len(validated_data)} company records")
        return validated_data
    
    def _is_company_data_valid(self, company_data: CompanyData) -> bool:
        """Check if company data meets validation criteria."""
        # Basic validation criteria
        if not company_data.name or len(company_data.name.strip()) < 3:
            return False
        
        if not company_data.country_code or len(company_data.country_code) != 2:
            return False
        
        # At least one identifier should be present
        if not company_data.vat_number and not company_data.lei_code:
            return False
        
        return True
    
    async def _load_cached_data(self):
        """Load cached company data from file."""
        cache_file = 'test_company_data_cache.json'
        
        try:
            if os.path.exists(cache_file):
                with open(cache_file, 'r') as f:
                    cache_data = json.load(f)
                
                # Convert dict back to CompanyData objects
                for company_id, data_dict in cache_data.get('companies', {}).items():
                    # Convert datetime strings back to datetime objects
                    if data_dict.get('last_validated'):
                        data_dict['last_validated'] = datetime.fromisoformat(data_dict['last_validated'])
                    
                    self.company_data_cache[company_id] = CompanyData(**data_dict)
                
                if cache_data.get('last_update'):
                    self.last_cache_update = datetime.fromisoformat(cache_data['last_update'])
                
                self.logger.info(f"Loaded {len(self.company_data_cache)} companies from cache")
                
        except Exception as e:
            self.logger.warning(f"Failed to load cached data: {str(e)}")
    
    async def _save_cached_data(self):
        """Save company data to cache file."""
        cache_file = 'test_company_data_cache.json'
        
        try:
            cache_data = {
                'last_update': self.last_cache_update.isoformat() if self.last_cache_update else None,
                'companies': {}
            }
            
            # Convert CompanyData objects to dict
            for company_id, company_data in self.company_data_cache.items():
                data_dict = asdict(company_data)
                # Convert datetime to string for JSON serialization
                if data_dict.get('last_validated'):
                    data_dict['last_validated'] = data_dict['last_validated'].isoformat()
                cache_data['companies'][company_id] = data_dict
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
            
            self.logger.info(f"Saved {len(self.company_data_cache)} companies to cache")
            
        except Exception as e:
            self.logger.error(f"Failed to save cached data: {str(e)}")
    
    async def get_companies_by_country(self, country_code: str) -> List[CompanyData]:
        """Get companies filtered by country code."""
        return [
            company for company in self.company_data_cache.values()
            if company.country_code == country_code
        ]
    
    async def get_companies_by_industry(self, industry: str) -> List[CompanyData]:
        """Get companies filtered by industry."""
        return [
            company for company in self.company_data_cache.values()
            if company.industry and industry.lower() in company.industry.lower()
        ]
    
    async def get_companies_with_valid_vat(self) -> List[CompanyData]:
        """Get companies with valid VAT numbers."""
        valid_companies = []
        
        for company in self.company_data_cache.values():
            vat_validation = company.additional_data.get('vat_validation', {})
            if vat_validation.get('valid', False):
                valid_companies.append(company)
        
        return valid_companies
    
    async def get_companies_with_valid_lei(self) -> List[CompanyData]:
        """Get companies with valid LEI codes."""
        valid_companies = []
        
        for company in self.company_data_cache.values():
            lei_validation = company.additional_data.get('lei_validation', {})
            if lei_validation.get('valid', False):
                valid_companies.append(company)
        
        return valid_companies
    
    async def refresh_company_data(self, max_age_hours: int = 24) -> Dict[str, CompanyData]:
        """Refresh company data if cache is older than specified hours."""
        if (self.last_cache_update is None or 
            datetime.utcnow() - self.last_cache_update > timedelta(hours=max_age_hours)):
            
            self.logger.info("Company data cache is stale, refreshing...")
            return await self.collect_real_company_data()
        else:
            self.logger.info("Company data cache is still fresh")
            return self.company_data_cache
    
    async def cleanup(self):
        """Cleanup test data manager resources."""
        self.logger.info("Cleaning up test data manager")
        
        if self.http_client:
            await self.http_client.aclose()
            self.http_client = None
        
        # Save final cache
        if self.company_data_cache:
            await self._save_cached_data()
        
        self.logger.info("Test data manager cleanup completed")