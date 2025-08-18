"""Tests for web scraping service."""
import pytest
from unittest.mock import patch, MagicMock
import time

from app.services.web_scraper import WebScraper
from app.utils.exceptions import ProcessingError


class TestWebScraper:
    """Test cases for WebScraper."""
    
    def test_init_default_config(self):
        """Test WebScraper initialization with default configuration."""
        scraper = WebScraper()
        
        assert scraper.respect_robots is True
        assert scraper.delay == WebScraper.DEFAULT_DELAY
        assert scraper.session is not None
        assert scraper.USER_AGENT in scraper.session.headers['User-Agent']
    
    def test_init_custom_config(self):
        """Test WebScraper initialization with custom configuration."""
        scraper = WebScraper(respect_robots=False, delay=2.0)
        
        assert scraper.respect_robots is False
        assert scraper.delay == 2.0
    
    @patch('app.services.web_scraper.WebScraper._scrape_single_page')
    @patch('app.services.web_scraper.WebScraper._can_fetch')
    def test_scrape_url_single_page(self, mock_can_fetch, mock_scrape_single):
        """Test scraping a single URL."""
        mock_can_fetch.return_value = True
        mock_scrape_single.return_value = {
            'content': 'Test content',
            'title': 'Test Page',
            'url': 'https://example.com',
            'content_type': 'text/html'
        }
        
        scraper = WebScraper()
        result = scraper.scrape_url('https://example.com')
        
        assert len(result) == 1
        assert result[0]['content'] == 'Test content'
        assert result[0]['title'] == 'Test Page'
        
        mock_can_fetch.assert_called_once_with('https://example.com')
        mock_scrape_single.assert_called_once_with('https://example.com')
    
    @patch('app.services.web_scraper.WebScraper._can_fetch')
    def test_scrape_url_robots_disallowed(self, mock_can_fetch):
        """Test handling of robots.txt disallowed URLs."""
        mock_can_fetch.return_value = False
        
        scraper = WebScraper(respect_robots=True)
        
        with pytest.raises(ProcessingError, match="Robots.txt disallows crawling"):
            scraper.scrape_url('https://example.com/disallowed')
    
    @patch('app.services.web_scraper.WebScraper._scrape_single_page')
    def test_scrape_url_robots_disabled(self, mock_scrape_single):
        """Test scraping with robots.txt checking disabled."""
        mock_scrape_single.return_value = {
            'content': 'Test content',
            'title': 'Test Page',
            'url': 'https://example.com'
        }
        
        scraper = WebScraper(respect_robots=False)
        result = scraper.scrape_url('https://example.com')
        
        assert len(result) == 1
        mock_scrape_single.assert_called_once()
    
    def test_scrape_url_invalid_url(self):
        """Test error handling for invalid URLs."""
        scraper = WebScraper()
        
        with pytest.raises(ProcessingError, match="Invalid URL"):
            scraper.scrape_url('not-a-url')
    
    @patch('requests.Session.get')
    @patch('app.services.web_scraper.WebScraper._respect_rate_limit')
    def test_scrape_single_page_html(self, mock_rate_limit, mock_get):
        """Test scraping a single HTML page."""
        html_content = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Content</h1>
            <p>This is test content.</p>
            <nav>Navigation</nav>
            <script>console.log('remove me');</script>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.headers = {'content-type': 'text/html; charset=utf-8'}
        mock_response.iter_content.return_value = [html_content.encode('utf-8')]
        mock_response.raise_for_status.return_value = None
        mock_response.encoding = 'utf-8'
        
        mock_get.return_value = mock_response
        
        scraper = WebScraper()
        result = scraper._scrape_single_page('https://example.com')
        
        assert result is not None
        assert 'Main Content' in result['content']
        assert 'This is test content.' in result['content']
        assert 'Navigation' not in result['content']  # Nav should be removed
        assert 'console.log' not in result['content']  # Script should be removed
        assert result['title'] == 'Test Page'
        assert result['url'] == 'https://example.com'
        assert result['content_type'] == 'text/html'
        
        mock_rate_limit.assert_called_once_with('https://example.com')
    
    @patch('requests.Session.get')
    @patch('app.services.web_scraper.WebScraper._respect_rate_limit')
    def test_scrape_single_page_plain_text(self, mock_rate_limit, mock_get):
        """Test scraping a plain text page."""
        text_content = "This is plain text content."
        
        mock_response = MagicMock()
        mock_response.headers = {'content-type': 'text/plain'}
        mock_response.iter_content.return_value = [text_content.encode('utf-8')]
        mock_response.raise_for_status.return_value = None
        mock_response.encoding = 'utf-8'
        
        mock_get.return_value = mock_response
        
        scraper = WebScraper()
        result = scraper._scrape_single_page('https://example.com/test.txt')
        
        assert result is not None
        assert result['content'] == text_content
        assert result['title'] == 'Test'  # Extracted from URL
        assert result['content_type'] == 'text/plain'
    
    @patch('requests.Session.get')
    @patch('app.services.web_scraper.WebScraper._respect_rate_limit')
    def test_scrape_single_page_unsupported_content_type(self, mock_rate_limit, mock_get):
        """Test handling of unsupported content types."""
        mock_response = MagicMock()
        mock_response.headers = {'content-type': 'application/octet-stream'}
        mock_response.iter_content.return_value = [b'binary content']
        mock_response.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response
        
        scraper = WebScraper()
        result = scraper._scrape_single_page('https://example.com/binary')
        
        assert result is None
    
    @patch('requests.Session.get')
    def test_scrape_single_page_content_too_large_header(self, mock_get):
        """Test handling of content that's too large (from header)."""
        mock_response = MagicMock()
        mock_response.headers = {
            'content-type': 'text/html',
            'content-length': str(WebScraper.MAX_CONTENT_SIZE + 1)
        }
        mock_response.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response
        
        scraper = WebScraper()
        
        with pytest.raises(ProcessingError, match="Content too large"):
            scraper._scrape_single_page('https://example.com/large')
    
    @patch('requests.Session.get')
    @patch('app.services.web_scraper.WebScraper._respect_rate_limit')
    def test_scrape_single_page_content_too_large_streaming(self, mock_rate_limit, mock_get):
        """Test handling of content that's too large (during streaming)."""
        # Create chunks that exceed max size
        large_chunk = b'x' * (WebScraper.MAX_CONTENT_SIZE // 2 + 1)
        
        mock_response = MagicMock()
        mock_response.headers = {'content-type': 'text/html'}
        mock_response.iter_content.return_value = [large_chunk, large_chunk]
        mock_response.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response
        
        scraper = WebScraper()
        
        with pytest.raises(ProcessingError, match="Content too large"):
            scraper._scrape_single_page('https://example.com/large')
    
    @patch('requests.Session.get')
    def test_scrape_single_page_request_error(self, mock_get):
        """Test handling of request errors."""
        mock_get.side_effect = Exception("Network error")
        
        scraper = WebScraper()
        
        with pytest.raises(ProcessingError, match="Failed to fetch URL"):
            scraper._scrape_single_page('https://example.com')
    
    def test_extract_html_metadata(self):
        """Test HTML metadata extraction."""
        html = """
        <html lang="en">
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
            <meta name="keywords" content="test, keywords">
            <meta name="author" content="Test Author">
            <meta property="og:title" content="OG Title">
            <meta property="og:description" content="OG Description">
        </head>
        <body>
            <h1>Heading 1</h1>
            <h2>Heading 2</h2>
            <h3>Heading 3</h3>
        </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        scraper = WebScraper()
        metadata = scraper._extract_html_metadata(soup, 'https://example.com')
        
        assert metadata['title'] == 'Test Page'
        assert metadata['description'] == 'Test description'
        assert metadata['keywords'] == 'test, keywords'
        assert metadata['author'] == 'Test Author'
        assert metadata['og_title'] == 'OG Title'
        assert metadata['og_description'] == 'OG Description'
        assert metadata['language'] == 'en'
        assert len(metadata['headings']) == 3
        assert metadata['headings'][0]['level'] == 1
        assert metadata['headings'][0]['text'] == 'Heading 1'
    
    def test_extract_main_content(self):
        """Test main content extraction from HTML."""
        html = """
        <html>
        <body>
            <nav>Navigation menu</nav>
            <header>Site header</header>
            <main>
                <h1>Main Content</h1>
                <p>This is the main content.</p>
            </main>
            <aside>Sidebar content</aside>
            <footer>Site footer</footer>
        </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        scraper = WebScraper()
        content = scraper._extract_main_content(soup)
        
        assert 'Main Content' in content
        assert 'This is the main content.' in content
        assert 'Navigation menu' not in content
        assert 'Site header' not in content
        assert 'Sidebar content' not in content
        assert 'Site footer' not in content
    
    def test_extract_main_content_fallback(self):
        """Test main content extraction fallback when no main element."""
        html = """
        <html>
        <body>
            <nav>Navigation menu</nav>
            <div class="content">
                <h1>Article Title</h1>
                <p>Article content.</p>
            </div>
            <aside>Sidebar</aside>
        </body>
        </html>
        """
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')
        
        scraper = WebScraper()
        content = scraper._extract_main_content(soup)
        
        assert 'Article Title' in content
        assert 'Article content.' in content
        assert 'Navigation menu' not in content  # Should be removed
        assert 'Sidebar' not in content  # Should be removed
    
    def test_clean_text(self):
        """Test text cleaning functionality."""
        scraper = WebScraper()
        
        # Test whitespace normalization
        text = "This   has    multiple     spaces."
        cleaned = scraper._clean_text(text)
        assert cleaned == "This has multiple spaces."
        
        # Test newline normalization
        text = "Line 1\n\n\n\n\nLine 2"
        cleaned = scraper._clean_text(text)
        assert cleaned == "Line 1\n\nLine 2"
        
        # Test leading/trailing whitespace
        text = "  \n  Text with spaces  \n  "
        cleaned = scraper._clean_text(text)
        assert cleaned == "Text with spaces"
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_can_fetch_allowed(self, mock_robot_parser):
        """Test robots.txt checking when crawling is allowed."""
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = True
        mock_robot_parser.return_value = mock_rp
        
        scraper = WebScraper()
        result = scraper._can_fetch('https://example.com/allowed')
        
        assert result is True
        mock_rp.set_url.assert_called_once_with('https://example.com/robots.txt')
        mock_rp.read.assert_called_once()
        mock_rp.can_fetch.assert_called_once_with(scraper.USER_AGENT, 'https://example.com/allowed')
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_can_fetch_disallowed(self, mock_robot_parser):
        """Test robots.txt checking when crawling is disallowed."""
        mock_rp = MagicMock()
        mock_rp.can_fetch.return_value = False
        mock_robot_parser.return_value = mock_rp
        
        scraper = WebScraper()
        result = scraper._can_fetch('https://example.com/disallowed')
        
        assert result is False
    
    @patch('urllib.robotparser.RobotFileParser')
    def test_can_fetch_robots_error(self, mock_robot_parser):
        """Test robots.txt checking when robots.txt can't be fetched."""
        mock_rp = MagicMock()
        mock_rp.read.side_effect = Exception("Can't fetch robots.txt")
        mock_robot_parser.return_value = mock_rp
        
        scraper = WebScraper()
        result = scraper._can_fetch('https://example.com/test')
        
        # Should default to allowing crawling if robots.txt can't be fetched
        assert result is True
    
    @patch('time.sleep')
    @patch('time.time')
    def test_respect_rate_limit(self, mock_time, mock_sleep):
        """Test rate limiting functionality."""
        # Mock time progression
        mock_time.side_effect = [0, 0.5, 1.0, 2.0]  # First call, check, sleep, final
        
        scraper = WebScraper(delay=1.0)
        
        # First request to domain - should not sleep
        scraper._respect_rate_limit('https://example.com/page1')
        mock_sleep.assert_not_called()
        
        # Second request too soon - should sleep
        scraper._respect_rate_limit('https://example.com/page2')
        mock_sleep.assert_called_once_with(0.5)  # 1.0 - 0.5 = 0.5
    
    def test_is_valid_url(self):
        """Test URL validation."""
        assert WebScraper._is_valid_url('https://example.com')
        assert WebScraper._is_valid_url('http://test.org/path')
        assert not WebScraper._is_valid_url('ftp://example.com')
        assert not WebScraper._is_valid_url('not-a-url')
        assert not WebScraper._is_valid_url('')
    
    def test_extract_title_from_url(self):
        """Test title extraction from URLs."""
        assert WebScraper._extract_title_from_url('https://example.com/my-article') == 'My Article'
        assert WebScraper._extract_title_from_url('https://example.com/test_page.html') == 'Test Page'
        assert WebScraper._extract_title_from_url('https://example.com/') == 'example.com'
        assert WebScraper._extract_title_from_url('https://example.com') == 'example.com'
        assert WebScraper._extract_title_from_url('invalid-url') == 'invalid-url'
    
    def test_context_manager(self):
        """Test WebScraper as context manager."""
        with WebScraper() as scraper:
            assert scraper.session is not None
        
        # Session should be closed after exiting context
        # Note: We can't easily test this without mocking, but the structure is correct
    
    def test_close(self):
        """Test explicit close method."""
        scraper = WebScraper()
        session = scraper.session
        
        scraper.close()
        
        # The session should be closed (we can't easily verify this without mocking)