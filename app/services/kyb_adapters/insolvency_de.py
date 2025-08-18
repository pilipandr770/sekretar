"""German Insolvency (Insolvenzbekanntmachungen) adapter for KYB monitoring."""
import re
import time
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from urllib.parse import urlencode, quote
from bs4 import BeautifulSoup
import structlog
from .base import BaseKYBAdapter, ValidationError, DataSourceUnavailable

logger = structlog.get_logger()


class GermanInsolvencyAdapter(BaseKYBAdapter):
    """
    Adapter for German insolvency notifications (Insolvenzbekanntmachungen).
    
    This adapter searches the official German insolvency register for companies
    and monitors for insolvency proceedings, including:
    - Insolvency applications
    - Insolvency proceedings opened
    - Insolvency proceedings closed
    - Asset liquidation notices
    """
    
    # Configuration
    RATE_LIMIT = 30  # 30 requests per minute to be respectful
    RATE_WINDOW = 60
    CACHE_TTL = 3600  # 1 hour cache
    MAX_RETRIES = 2
    RETRY_DELAY = 2
    
    # German insolvency register base URL
    BASE_URL = "https://www.insolvenzbekanntmachungen.de"
    SEARCH_URL = f"{BASE_URL}/ap/suche.jsf"
    
    def __init__(self, redis_client=None):
        """Initialize German insolvency adapter."""
        super().__init__(redis_client)
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'AI-Secretary-KYB/1.0 (Compliance Monitoring)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        })
    
    def check_single(self, company_name: str, **kwargs) -> Dict[str, Any]:
        """
        Check a single company for insolvency proceedings.
        
        Args:
            company_name: Company name to search for
            **kwargs: Additional search parameters:
                - registration_number: Company registration number
                - city: Company city
                - postal_code: Company postal code
                - date_from: Search from date (YYYY-MM-DD)
                - date_to: Search to date (YYYY-MM-DD)
        
        Returns:
            Dict with insolvency check results
        """
        start_time = time.time()
        
        try:
            # Validate and clean company name
            company_name = self._validate_identifier(company_name)
            
            # Check rate limit
            if not self._check_rate_limit():
                raise DataSourceUnavailable("Rate limit exceeded for German insolvency API")
            
            # Check cache first
            cache_key = self._get_cache_key(company_name, **kwargs)
            cached_result = self._get_cached_result(cache_key)
            if cached_result:
                return cached_result
            
            # Perform the search
            result = self._execute_with_retry(
                self._search_insolvency_proceedings,
                company_name,
                **kwargs
            )
            
            # Add metadata
            result.update({
                'identifier': company_name,
                'source': 'INSOLVENCY_DE',
                'checked_at': datetime.utcnow().isoformat() + 'Z',
                'response_time_ms': int((time.time() - start_time) * 1000)
            })
            
            # Cache the result
            self._cache_result(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking German insolvency for {company_name}", error=str(e))
            return self._create_error_result(company_name, str(e))
    
    def _validate_identifier(self, identifier: str) -> str:
        """Validate and clean company name for German insolvency search."""
        if not identifier or not identifier.strip():
            raise ValidationError("Company name cannot be empty")
        
        # Clean the company name
        cleaned = identifier.strip()
        
        # Remove common German company suffixes for better matching
        suffixes = ['GmbH', 'AG', 'KG', 'OHG', 'GbR', 'UG', 'e.V.', 'mbH']
        for suffix in suffixes:
            if cleaned.upper().endswith(suffix.upper()):
                # Keep the suffix but normalize it
                cleaned = cleaned[:-len(suffix)].strip() + ' ' + suffix
                break
        
        return cleaned
    
    def _search_insolvency_proceedings(self, company_name: str, **kwargs) -> Dict[str, Any]:
        """
        Search for insolvency proceedings for a company.
        
        Args:
            company_name: Company name to search
            **kwargs: Additional search parameters
        
        Returns:
            Dict with search results
        """
        try:
            # Prepare search parameters
            search_params = self._prepare_search_params(company_name, **kwargs)
            
            # Perform the search request
            response = self.session.get(
                self.SEARCH_URL,
                params=search_params,
                timeout=15
            )
            
            if response.status_code != 200:
                return {
                    'status': 'error',
                    'error': f'HTTP {response.status_code}: {response.reason}',
                    'proceedings_found': False,
                    'proceedings': []
                }
            
            # Parse the response
            proceedings = self._parse_search_results(response.text, company_name)
            
            # Determine status
            status = 'found' if proceedings else 'not_found'
            
            return {
                'status': status,
                'proceedings_found': len(proceedings) > 0,
                'proceedings_count': len(proceedings),
                'proceedings': proceedings,
                'search_params': search_params
            }
            
        except requests.exceptions.Timeout:
            return {
                'status': 'timeout',
                'error': 'Request timeout (15s)',
                'proceedings_found': False,
                'proceedings': []
            }
        except requests.exceptions.ConnectionError:
            return {
                'status': 'connection_error',
                'error': 'Cannot connect to insolvency register',
                'proceedings_found': False,
                'proceedings': []
            }
        except Exception as e:
            logger.error(f"Error searching insolvency proceedings", error=str(e))
            return {
                'status': 'error',
                'error': str(e),
                'proceedings_found': False,
                'proceedings': []
            }
    
    def _prepare_search_params(self, company_name: str, **kwargs) -> Dict[str, str]:
        """Prepare search parameters for the insolvency register."""
        params = {
            'suchTyp': 'SCHULDNER',  # Search for debtor
            'schuldnerName': company_name,
            'sort': 'DATUM_DESC'  # Sort by date descending
        }
        
        # Add optional parameters
        if kwargs.get('registration_number'):
            params['registerNummer'] = kwargs['registration_number']
        
        if kwargs.get('city'):
            params['ort'] = kwargs['city']
        
        if kwargs.get('postal_code'):
            params['plz'] = kwargs['postal_code']
        
        # Date range (default to last 2 years if not specified)
        date_from = kwargs.get('date_from')
        date_to = kwargs.get('date_to')
        
        if not date_from:
            # Default to 2 years ago
            date_from = (datetime.now() - timedelta(days=730)).strftime('%d.%m.%Y')
        
        if not date_to:
            # Default to today
            date_to = datetime.now().strftime('%d.%m.%Y')
        
        params['datumVon'] = date_from
        params['datumBis'] = date_to
        
        return params
    
    def _parse_search_results(self, html_content: str, company_name: str) -> List[Dict[str, Any]]:
        """
        Parse HTML search results from the insolvency register.
        
        Args:
            html_content: HTML content from search response
            company_name: Original company name searched for
        
        Returns:
            List of insolvency proceedings found
        """
        proceedings = []
        
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Look for result table or result entries
            # The exact structure may vary, so we'll look for common patterns
            
            # Method 1: Look for table rows with insolvency data
            result_rows = soup.find_all('tr', class_=re.compile(r'result|entry|row'))
            
            if not result_rows:
                # Method 2: Look for div containers with insolvency data
                result_rows = soup.find_all('div', class_=re.compile(r'result|entry|item'))
            
            for row in result_rows:
                proceeding = self._parse_proceeding_row(row, company_name)
                if proceeding:
                    proceedings.append(proceeding)
            
            # If no structured results found, try text-based parsing
            if not proceedings:
                proceedings = self._parse_text_results(html_content, company_name)
            
        except Exception as e:
            logger.error(f"Error parsing insolvency search results", error=str(e))
        
        return proceedings
    
    def _parse_proceeding_row(self, row_element, company_name: str) -> Optional[Dict[str, Any]]:
        """
        Parse a single proceeding row/element.
        
        Args:
            row_element: BeautifulSoup element containing proceeding data
            company_name: Original company name for matching
        
        Returns:
            Dict with proceeding data or None if not valid
        """
        try:
            # Extract text content
            text_content = row_element.get_text(separator=' ', strip=True)
            
            # Skip if this doesn't look like a relevant result
            if not self._is_relevant_result(text_content, company_name):
                return None
            
            # Extract key information using regex patterns
            proceeding = {
                'raw_text': text_content,
                'company_name': self._extract_company_name(text_content),
                'proceeding_type': self._extract_proceeding_type(text_content),
                'court': self._extract_court(text_content),
                'case_number': self._extract_case_number(text_content),
                'date': self._extract_date(text_content),
                'status': self._extract_status(text_content),
                'details': self._extract_additional_details(text_content)
            }
            
            # Only return if we found essential information
            if proceeding['company_name'] or proceeding['case_number']:
                return proceeding
            
        except Exception as e:
            logger.warning(f"Error parsing proceeding row", error=str(e))
        
        return None
    
    def _is_relevant_result(self, text: str, company_name: str) -> bool:
        """Check if the result text is relevant to our search."""
        text_lower = text.lower()
        company_lower = company_name.lower()
        
        # Check if company name appears in the text
        if company_lower in text_lower:
            return True
        
        # Check for partial matches (remove common suffixes)
        company_base = re.sub(r'\s+(gmbh|ag|kg|ohg|gbr|ug|e\.v\.|mbh)$', '', company_lower, flags=re.IGNORECASE)
        if company_base and company_base in text_lower:
            return True
        
        # Check for insolvency-related keywords
        insolvency_keywords = [
            'insolvenz', 'konkurs', 'verfahren', 'eröffnung', 'einstellung',
            'aufhebung', 'verwaltung', 'verwalter', 'gläubiger'
        ]
        
        if any(keyword in text_lower for keyword in insolvency_keywords):
            return True
        
        return False
    
    def _extract_company_name(self, text: str) -> Optional[str]:
        """Extract company name from proceeding text."""
        # Look for patterns like "Firma: Company Name" or similar
        patterns = [
            r'(?:firma|unternehmen|gesellschaft|schuldner):\s*([^,\n]+)',
            r'\b([A-ZÄÖÜ][a-zäöüß]*\s+(?:GmbH|AG|KG|OHG|GbR|UG|e\.V\.|mbH))\b',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_proceeding_type(self, text: str) -> Optional[str]:
        """Extract proceeding type from text."""
        types = {
            'eröffnung': 'opening',
            'einstellung': 'termination',
            'aufhebung': 'cancellation',
            'antrag': 'application',
            'verwaltung': 'administration',
            'liquidation': 'liquidation',
            'verkauf': 'sale'
        }
        
        text_lower = text.lower()
        for german_type, english_type in types.items():
            if german_type in text_lower:
                return english_type
        
        return 'unknown'
    
    def _extract_court(self, text: str) -> Optional[str]:
        """Extract court name from text."""
        # Look for patterns like "Amtsgericht München" or "AG München"
        court_pattern = r'(?:amtsgericht|ag|landgericht|lg)\s+([a-zäöüß\s]+)'
        match = re.search(court_pattern, text, re.IGNORECASE)
        if match:
            return match.group(0).strip()
        
        return None
    
    def _extract_case_number(self, text: str) -> Optional[str]:
        """Extract case number from text."""
        # Look for patterns like "12 IN 345/23" or similar
        case_patterns = [
            r'\b\d+\s+IN\s+\d+/\d+\b',
            r'\b\d+\s+HRB\s+\d+/\d+\b',
            r'Az\.?\s*:?\s*(\d+\s+[A-Z]+\s+\d+/\d+)',
        ]
        
        for pattern in case_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.groups():
                    return match.group(1).strip()
                else:
                    return match.group(0).strip()
        
        return None
    
    def _extract_date(self, text: str) -> Optional[str]:
        """Extract date from text."""
        # Look for German date patterns
        date_patterns = [
            r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b',
            r'\b(\d{4})-(\d{1,2})-(\d{1,2})\b'
        ]
        
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                if '.' in match.group(0):
                    # German format DD.MM.YYYY
                    day, month, year = match.groups()
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                else:
                    # ISO format YYYY-MM-DD
                    return match.group(0)
        
        return None
    
    def _extract_status(self, text: str) -> str:
        """Extract proceeding status from text."""
        text_lower = text.lower()
        
        if any(word in text_lower for word in ['eröffnet', 'eröffnung']):
            return 'opened'
        elif any(word in text_lower for word in ['eingestellt', 'einstellung']):
            return 'terminated'
        elif any(word in text_lower for word in ['aufgehoben', 'aufhebung']):
            return 'cancelled'
        elif any(word in text_lower for word in ['beantragt', 'antrag']):
            return 'applied'
        elif any(word in text_lower for word in ['abgeschlossen', 'beendet']):
            return 'completed'
        else:
            return 'unknown'
    
    def _extract_additional_details(self, text: str) -> Dict[str, Any]:
        """Extract additional details from text."""
        details = {}
        
        # Look for administrator/trustee information
        admin_pattern = r'(?:verwalter|treuhänder):\s*([^,\n]+)'
        admin_match = re.search(admin_pattern, text, re.IGNORECASE)
        if admin_match:
            details['administrator'] = admin_match.group(1).strip()
        
        # Look for asset information
        if 'vermögen' in text.lower():
            details['assets_mentioned'] = True
        
        # Look for creditor information
        if 'gläubiger' in text.lower():
            details['creditors_mentioned'] = True
        
        return details
    
    def _parse_text_results(self, html_content: str, company_name: str) -> List[Dict[str, Any]]:
        """
        Fallback text-based parsing when structured parsing fails.
        
        Args:
            html_content: HTML content to parse
            company_name: Company name to search for
        
        Returns:
            List of proceedings found through text parsing
        """
        proceedings = []
        
        try:
            # Remove HTML tags and get plain text
            soup = BeautifulSoup(html_content, 'html.parser')
            text_content = soup.get_text(separator='\n', strip=True)
            
            # Split into lines and look for relevant entries
            lines = text_content.split('\n')
            
            current_proceeding = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Check if this line starts a new proceeding
                if self._is_relevant_result(line, company_name):
                    # Save previous proceeding if exists
                    if current_proceeding:
                        proceedings.append(current_proceeding)
                    
                    # Start new proceeding
                    current_proceeding = {
                        'raw_text': line,
                        'company_name': self._extract_company_name(line),
                        'proceeding_type': self._extract_proceeding_type(line),
                        'court': self._extract_court(line),
                        'case_number': self._extract_case_number(line),
                        'date': self._extract_date(line),
                        'status': self._extract_status(line),
                        'details': self._extract_additional_details(line)
                    }
                elif current_proceeding:
                    # Add to current proceeding
                    current_proceeding['raw_text'] += ' ' + line
                    
                    # Update fields if found in this line
                    if not current_proceeding.get('company_name'):
                        current_proceeding['company_name'] = self._extract_company_name(line)
                    if not current_proceeding.get('court'):
                        current_proceeding['court'] = self._extract_court(line)
                    if not current_proceeding.get('case_number'):
                        current_proceeding['case_number'] = self._extract_case_number(line)
                    if not current_proceeding.get('date'):
                        current_proceeding['date'] = self._extract_date(line)
            
            # Add the last proceeding
            if current_proceeding:
                proceedings.append(current_proceeding)
            
        except Exception as e:
            logger.error(f"Error in text-based parsing", error=str(e))
        
        return proceedings
    
    def get_proceeding_details(self, case_number: str, court: str = None) -> Dict[str, Any]:
        """
        Get detailed information about a specific insolvency proceeding.
        
        Args:
            case_number: Case number of the proceeding
            court: Optional court name for more specific search
        
        Returns:
            Dict with detailed proceeding information
        """
        try:
            # This would implement detailed proceeding lookup
            # For now, return basic structure
            return {
                'case_number': case_number,
                'court': court,
                'status': 'details_not_implemented',
                'error': 'Detailed proceeding lookup not yet implemented'
            }
        except Exception as e:
            return {
                'case_number': case_number,
                'status': 'error',
                'error': str(e)
            }
    
    def monitor_proceeding_changes(self, case_number: str) -> Dict[str, Any]:
        """
        Monitor changes in a specific insolvency proceeding.
        
        Args:
            case_number: Case number to monitor
        
        Returns:
            Dict with monitoring results
        """
        try:
            # This would implement proceeding change monitoring
            # For now, return basic structure
            return {
                'case_number': case_number,
                'status': 'monitoring_not_implemented',
                'error': 'Proceeding change monitoring not yet implemented'
            }
        except Exception as e:
            return {
                'case_number': case_number,
                'status': 'error',
                'error': str(e)
            }