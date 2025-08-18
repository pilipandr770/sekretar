"""Web scraping service for extracting content from URLs."""
import re
import time
import logging
from typing import List, Dict, Any, Optional, Set
from urllib.parse import urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter

try:
    from bs4 import BeautifulSoup, Comment
    HAS_BS4 = True
except ImportError:
    BeautifulSoup = None
    Comment = None
    HAS_BS4 = False
from urllib3.util.retry import Retry

from app.utils.exceptions import ProcessingError


logger = logging.getLogger(__name__)


class WebScraper:
    """Service for scraping web content with respect for robots.txt and rate limiting."""
    
    # Default configuration
    DEFAULT_TIMEOUT = 30
    DEFAULT_DELAY = 1.0  # seconds between requests
    MAX_RETRIES = 3
    MAX_REDIRECTS = 10
    MAX_CONTENT_SIZE = 16 * 1024 * 1024  # 16MB
    
    # User agent string
    USER_AGENT = 'AI-Secretary-Bot/1.0 (Knowledge Base Crawler; +https://ai-secretary.com/bot)'
    
    # Content type patterns to accept
    ACCEPTED_CONTENT_TYPES = {
        'text/html',
        'application/xhtml+xml',
        'text/plain',
        'text/markdown',
        'application/pdf'
    }
    
    def __init__(self, respect_robots: bool = True, delay: float = None):
        """
        Initialize web scraper.
        
        Args:
            respect_robots: Whether to respect robots.txt
            delay: Delay between requests in seconds
        """
        self.respect_robots = respect_robots
        self.delay = delay or self.DEFAULT_DELAY
        self.robots_cache = {}  # Cache for robots.txt files
        self.last_request_time = {}  # Track last request time per domain
        
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=self.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Set default headers
        self.session.headers.update({
            'User-Agent': self.USER_AGENT,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,text/plain;q=0.8,*/*;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
    
    def scrape_url(self, url: str, max_depth: int = 1) -> List[Dict[str, Any]]:
        """
        Scrape content from a URL.
        
        Args:
            url: URL to scrape
            max_depth: Maximum depth for following links (1 = single page only)
            
        Returns:
            List of scraped content dictionaries
        """
        try:
            # Validate URL
            if not self._is_valid_url(url):
                raise ProcessingError(f"Invalid URL: {url}")
            
            # Check robots.txt if enabled
            if self.respect_robots and not self._can_fetch(url):
                raise ProcessingError(f"Robots.txt disallows crawling: {url}")
            
            # Scrape single page
            content = self._scrape_single_page(url)
            
            if max_depth <= 1:
                return [content] if content else []
            
            # TODO: Implement multi-depth crawling
            # For now, just return single page
            logger.warning(f"Multi-depth crawling not yet implemented (max_depth={max_depth})")
            return [content] if content else []
            
        except ProcessingError:
            raise
        except Exception as e:
            logger.error(f"Failed to scrape URL {url}: {str(e)}")
            raise ProcessingError(f"Failed to scrape URL: {str(e)}")
    
    def _scrape_single_page(self, url: str) -> Optional[Dict[str, Any]]:
        """Scrape content from a single page."""
        try:
            # Rate limiting
            self._respect_rate_limit(url)
            
            # Make request
            response = self.session.get(
                url,
                timeout=self.DEFAULT_TIMEOUT,
                stream=True,
                allow_redirects=True
            )
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if not any(accepted in content_type for accepted in self.ACCEPTED_CONTENT_TYPES):
                logger.warning(f"Unsupported content type: {content_type} for {url}")
                return None
            
            # Check content length
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self.MAX_CONTENT_SIZE:
                raise ProcessingError(f"Content too large: {content_length} bytes")
            
            # Read content with size limit
            content_bytes = b''
            for chunk in response.iter_content(chunk_size=8192):
                content_bytes += chunk
                if len(content_bytes) > self.MAX_CONTENT_SIZE:
                    raise ProcessingError("Content too large")
            
            # Process content based on type
            if 'text/html' in content_type or 'application/xhtml+xml' in content_type:
                return self._process_html_content(content_bytes, url, response.encoding)
            elif 'text/plain' in content_type:
                return self._process_text_content(content_bytes, url, response.encoding)
            elif 'text/markdown' in content_type:
                return self._process_markdown_content(content_bytes, url, response.encoding)
            elif 'application/pdf' in content_type:
                return self._process_pdf_content(content_bytes, url)
            else:
                logger.warning(f"Unhandled content type: {content_type} for {url}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"HTTP error for {url}: {str(e)}")
            raise ProcessingError(f"Failed to fetch URL: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing {url}: {str(e)}")
            raise ProcessingError(f"Failed to process content: {str(e)}")
    
    def _process_html_content(self, content_bytes: bytes, url: str, encoding: str = None) -> Dict[str, Any]:
        """Process HTML content and extract text."""
        if not HAS_BS4:
            raise ProcessingError("HTML processing not available. Please install beautifulsoup4.")
        
        try:
            # Decode content
            if encoding:
                try:
                    html_content = content_bytes.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    html_content = content_bytes.decode('utf-8', errors='ignore')
            else:
                html_content = content_bytes.decode('utf-8', errors='ignore')
            
            # Parse HTML
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()
            
            # Remove comments
            for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
                comment.extract()
            
            # Extract metadata
            metadata = self._extract_html_metadata(soup, url)
            
            # Extract main content
            content_text = self._extract_main_content(soup)
            
            # Clean up text
            content_text = self._clean_text(content_text)
            
            if not content_text.strip():
                logger.warning(f"No text content extracted from {url}")
                return None
            
            return {
                'content': content_text,
                'title': metadata.get('title', self._extract_title_from_url(url)),
                'url': url,
                'content_type': 'text/html',
                'metadata': metadata
            }
            
        except Exception as e:
            logger.error(f"Failed to process HTML content from {url}: {str(e)}")
            raise ProcessingError(f"Failed to process HTML content: {str(e)}")
    
    def _process_text_content(self, content_bytes: bytes, url: str, encoding: str = None) -> Dict[str, Any]:
        """Process plain text content."""
        try:
            # Decode content
            if encoding:
                try:
                    text_content = content_bytes.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    text_content = content_bytes.decode('utf-8', errors='ignore')
            else:
                text_content = content_bytes.decode('utf-8', errors='ignore')
            
            # Clean up text
            text_content = self._clean_text(text_content)
            
            if not text_content.strip():
                return None
            
            return {
                'content': text_content,
                'title': self._extract_title_from_url(url),
                'url': url,
                'content_type': 'text/plain',
                'metadata': {
                    'format': 'plain_text',
                    'lines': len(text_content.split('\n'))
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process text content from {url}: {str(e)}")
            raise ProcessingError(f"Failed to process text content: {str(e)}")
    
    def _process_markdown_content(self, content_bytes: bytes, url: str, encoding: str = None) -> Dict[str, Any]:
        """Process Markdown content."""
        try:
            # Decode content
            if encoding:
                try:
                    md_content = content_bytes.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    md_content = content_bytes.decode('utf-8', errors='ignore')
            else:
                md_content = content_bytes.decode('utf-8', errors='ignore')
            
            # Extract title from first heading
            title = self._extract_title_from_url(url)
            lines = md_content.split('\n')
            for line in lines[:10]:
                if line.startswith('# '):
                    title = line[2:].strip()
                    break
            
            return {
                'content': md_content,
                'title': title,
                'url': url,
                'content_type': 'text/markdown',
                'metadata': {
                    'format': 'markdown',
                    'lines': len(lines)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process Markdown content from {url}: {str(e)}")
            raise ProcessingError(f"Failed to process Markdown content: {str(e)}")
    
    def _process_pdf_content(self, content_bytes: bytes, url: str) -> Dict[str, Any]:
        """Process PDF content."""
        try:
            # For PDF processing, we'd use the DocumentProcessor
            # For now, return a placeholder
            return {
                'content': f"[PDF content from {url}]",
                'title': self._extract_title_from_url(url),
                'url': url,
                'content_type': 'application/pdf',
                'metadata': {
                    'format': 'pdf',
                    'size': len(content_bytes)
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to process PDF content from {url}: {str(e)}")
            raise ProcessingError(f"Failed to process PDF content: {str(e)}")
    
    def _extract_html_metadata(self, soup, url: str) -> Dict[str, Any]:
        """Extract metadata from HTML."""
        if not HAS_BS4:
            return {'url': url}
        
        metadata = {'url': url}
        
        # Title
        title_tag = soup.find('title')
        if title_tag:
            metadata['title'] = title_tag.get_text().strip()
        
        # Meta tags
        meta_tags = soup.find_all('meta')
        for meta in meta_tags:
            name = meta.get('name', '').lower()
            property_name = meta.get('property', '').lower()
            content = meta.get('content', '').strip()
            
            if not content:
                continue
            
            if name == 'description':
                metadata['description'] = content
            elif name == 'keywords':
                metadata['keywords'] = content
            elif name == 'author':
                metadata['author'] = content
            elif property_name == 'og:title':
                metadata['og_title'] = content
            elif property_name == 'og:description':
                metadata['og_description'] = content
            elif property_name == 'og:type':
                metadata['og_type'] = content
        
        # Language
        html_tag = soup.find('html')
        if html_tag and html_tag.get('lang'):
            metadata['language'] = html_tag.get('lang')
        
        # Headings structure
        headings = []
        for level in range(1, 7):
            for heading in soup.find_all(f'h{level}'):
                text = heading.get_text().strip()
                if text:
                    headings.append({'level': level, 'text': text})
        
        if headings:
            metadata['headings'] = headings[:10]  # Limit to first 10 headings
        
        return metadata
    
    def _extract_main_content(self, soup) -> str:
        """Extract main content from HTML, trying to avoid navigation and ads."""
        if not HAS_BS4:
            return ""
        
        # Try to find main content containers
        main_selectors = [
            'main',
            'article',
            '[role="main"]',
            '.main-content',
            '.content',
            '.post-content',
            '.entry-content',
            '#content',
            '#main'
        ]
        
        main_content = None
        for selector in main_selectors:
            main_content = soup.select_one(selector)
            if main_content:
                break
        
        # If no main content found, use body but remove common non-content elements
        if not main_content:
            main_content = soup.find('body') or soup
            
            # Remove common non-content elements
            for selector in ['nav', 'header', 'footer', 'aside', '.sidebar', '.navigation', '.menu']:
                for element in main_content.select(selector):
                    element.decompose()
        
        # Extract text
        text = main_content.get_text(separator='\n', strip=True)
        
        return text
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content."""
        if not text:
            return ""
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove excessive newlines
        text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _can_fetch(self, url: str) -> bool:
        """Check if URL can be fetched according to robots.txt."""
        try:
            parsed_url = urlparse(url)
            base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
            
            # Check cache first
            if base_url in self.robots_cache:
                rp = self.robots_cache[base_url]
            else:
                # Fetch and parse robots.txt
                robots_url = urljoin(base_url, '/robots.txt')
                rp = RobotFileParser()
                rp.set_url(robots_url)
                
                try:
                    rp.read()
                    self.robots_cache[base_url] = rp
                except Exception as e:
                    logger.warning(f"Failed to fetch robots.txt from {robots_url}: {str(e)}")
                    # If we can't fetch robots.txt, assume we can crawl
                    return True
            
            # Check if we can fetch the URL
            return rp.can_fetch(self.USER_AGENT, url)
            
        except Exception as e:
            logger.warning(f"Error checking robots.txt for {url}: {str(e)}")
            # If there's an error, assume we can crawl
            return True
    
    def _respect_rate_limit(self, url: str):
        """Implement rate limiting per domain."""
        try:
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            
            current_time = time.time()
            
            if domain in self.last_request_time:
                time_since_last = current_time - self.last_request_time[domain]
                if time_since_last < self.delay:
                    sleep_time = self.delay - time_since_last
                    logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s for {domain}")
                    time.sleep(sleep_time)
            
            self.last_request_time[domain] = time.time()
            
        except Exception as e:
            logger.warning(f"Error in rate limiting for {url}: {str(e)}")
    
    @staticmethod
    def _is_valid_url(url: str) -> bool:
        """Validate URL format."""
        try:
            result = urlparse(url)
            return all([result.scheme in ['http', 'https'], result.netloc])
        except Exception:
            return False
    
    @staticmethod
    def _extract_title_from_url(url: str) -> str:
        """Extract a title from URL."""
        try:
            parsed = urlparse(url)
            path = parsed.path.strip('/')
            
            if path:
                # Use last part of path as title
                title = path.split('/')[-1]
                # Remove file extension
                title = re.sub(r'\.[^.]+$', '', title)
                # Replace hyphens and underscores with spaces
                title = re.sub(r'[-_]+', ' ', title)
                # Capitalize words
                title = ' '.join(word.capitalize() for word in title.split())
                return title or parsed.netloc
            else:
                return parsed.netloc
                
        except Exception:
            return url
    
    def close(self):
        """Close the session."""
        if hasattr(self, 'session'):
            self.session.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()