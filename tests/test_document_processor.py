"""Tests for document processing service."""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from io import BytesIO

from app.services.document_processor import DocumentProcessor
from app.utils.exceptions import ProcessingError


class TestDocumentProcessor:
    """Test cases for DocumentProcessor."""
    
    def test_extract_text_from_plain_text_file(self):
        """Test extracting text from plain text file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            test_content = "This is a test document.\nWith multiple lines."
            f.write(test_content)
            f.flush()
            temp_path = f.name
        
        try:
            result = DocumentProcessor.extract_text_from_file(temp_path, 'text/plain')
            
            assert result['content'] == test_content
            assert result['token_count'] > 0
            assert result['content_hash'] is not None
            assert result['file_extension'] == 'txt'
            assert result['metadata']['format'] == 'plain_text'
            
        finally:
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass  # Ignore cleanup errors on Windows
    
    def test_extract_text_from_markdown_file(self):
        """Test extracting text from Markdown file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            test_content = "# Test Document\n\nThis is a **markdown** document."
            f.write(test_content)
            f.flush()
            temp_path = f.name
        
        try:
            result = DocumentProcessor.extract_text_from_file(temp_path, 'text/markdown')
            
            assert result['content'] == test_content
            assert result['metadata']['title'] == 'Test Document'
            assert result['metadata']['format'] == 'markdown'
            
        finally:
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass
    
    def test_extract_text_from_html_file(self):
        """Test extracting text from HTML file."""
        html_content = """
        <html>
        <head><title>Test Page</title></head>
        <body>
            <h1>Main Heading</h1>
            <p>This is a paragraph.</p>
            <script>console.log('should be removed');</script>
        </body>
        </html>
        """
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            f.write(html_content)
            f.flush()
            temp_path = f.name
        
        try:
            result = DocumentProcessor.extract_text_from_file(temp_path, 'text/html')
            
            assert 'Main Heading' in result['content']
            assert 'This is a paragraph.' in result['content']
            assert 'should be removed' not in result['content']  # Script removed
            assert result['metadata']['title'] == 'Test Page'
            
        finally:
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass
    
    @patch('PyPDF2.PdfReader')
    def test_extract_text_from_pdf_file(self, mock_pdf_reader):
        """Test extracting text from PDF file."""
        # Mock PDF reader
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "This is page 1 content."
        
        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_reader_instance.metadata = {'/Title': 'Test PDF', '/Author': 'Test Author'}
        
        mock_pdf_reader.return_value = mock_reader_instance
        
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as f:
            f.write(b'fake pdf content')
            f.flush()
            temp_path = f.name
        
        try:
            result = DocumentProcessor.extract_text_from_file(temp_path, 'application/pdf')
            
            assert '[Page 1]' in result['content']
            assert 'This is page 1 content.' in result['content']
            assert result['metadata']['title'] == 'Test PDF'
            assert result['metadata']['author'] == 'Test Author'
            assert result['metadata']['pages'] == 1
            
        finally:
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass
    
    @patch('docx.Document')
    def test_extract_text_from_docx_file(self, mock_docx):
        """Test extracting text from DOCX file."""
        # Mock DOCX document
        mock_paragraph1 = MagicMock()
        mock_paragraph1.text = "First paragraph."
        
        mock_paragraph2 = MagicMock()
        mock_paragraph2.text = "Second paragraph."
        
        mock_doc = MagicMock()
        mock_doc.paragraphs = [mock_paragraph1, mock_paragraph2]
        mock_doc.core_properties.title = "Test Document"
        mock_doc.core_properties.author = "Test Author"
        
        mock_docx.return_value = mock_doc
        
        with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as f:
            f.write(b'fake docx content')
            f.flush()
            temp_path = f.name
        
        try:
            result = DocumentProcessor.extract_text_from_file(temp_path)
            
            assert 'First paragraph.' in result['content']
            assert 'Second paragraph.' in result['content']
            assert result['metadata']['title'] == 'Test Document'
            assert result['metadata']['author'] == 'Test Author'
            
        finally:
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass
    
    def test_extract_text_file_not_found(self):
        """Test error handling for non-existent file."""
        with pytest.raises(ProcessingError, match="File not found"):
            DocumentProcessor.extract_text_from_file("/nonexistent/file.txt")
    
    def test_extract_text_file_too_large(self):
        """Test error handling for files that are too large."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            # Create a large file
            large_content = "x" * (DocumentProcessor.MAX_FILE_SIZE + 1)
            f.write(large_content)
            f.flush()
            temp_path = f.name
        
        try:
            with pytest.raises(ProcessingError, match="File too large"):
                DocumentProcessor.extract_text_from_file(temp_path)
        finally:
            try:
                os.unlink(temp_path)
            except (OSError, PermissionError):
                pass
    
    @patch('requests.get')
    def test_extract_text_from_url_html(self, mock_get):
        """Test extracting text from HTML URL."""
        html_content = """
        <html>
        <head><title>Web Page</title></head>
        <body>
            <h1>Main Content</h1>
            <p>This is web content.</p>
        </body>
        </html>
        """
        
        mock_response = MagicMock()
        mock_response.headers = {'content-type': 'text/html; charset=utf-8'}
        mock_response.iter_content.return_value = [html_content.encode('utf-8')]
        mock_response.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response
        
        result = DocumentProcessor.extract_text_from_url("https://example.com/test")
        
        assert len(result) == 1
        assert 'Main Content' in result[0]['content']
        assert 'This is web content.' in result[0]['content']
        assert result[0]['title'] == 'Web Page'
        assert result[0]['url'] == 'https://example.com/test'
    
    @patch('requests.get')
    def test_extract_text_from_url_plain_text(self, mock_get):
        """Test extracting text from plain text URL."""
        text_content = "This is plain text content from a URL."
        
        mock_response = MagicMock()
        mock_response.headers = {'content-type': 'text/plain'}
        mock_response.iter_content.return_value = [text_content.encode('utf-8')]
        mock_response.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response
        
        result = DocumentProcessor.extract_text_from_url("https://example.com/test.txt")
        
        assert len(result) == 1
        assert result[0]['content'] == text_content
        assert result[0]['title'] == 'Test'  # Extracted from URL
    
    @patch('requests.get')
    def test_extract_text_from_url_invalid_url(self, mock_get):
        """Test error handling for invalid URL."""
        with pytest.raises(ProcessingError, match="Invalid URL"):
            DocumentProcessor.extract_text_from_url("not-a-url")
    
    @patch('requests.get')
    def test_extract_text_from_url_request_error(self, mock_get):
        """Test error handling for request errors."""
        mock_get.side_effect = Exception("Network error")
        
        with pytest.raises(ProcessingError, match="Failed to fetch URL"):
            DocumentProcessor.extract_text_from_url("https://example.com/test")
    
    @patch('requests.get')
    def test_extract_text_from_url_content_too_large(self, mock_get):
        """Test error handling for content that's too large."""
        mock_response = MagicMock()
        mock_response.headers = {
            'content-type': 'text/plain',
            'content-length': str(DocumentProcessor.MAX_FILE_SIZE + 1)
        }
        mock_response.raise_for_status.return_value = None
        
        mock_get.return_value = mock_response
        
        with pytest.raises(ProcessingError, match="Content too large"):
            DocumentProcessor.extract_text_from_url("https://example.com/large-file")
    
    def test_chunk_text_single_chunk(self):
        """Test chunking text that fits in a single chunk."""
        short_text = "This is a short text that should fit in one chunk."
        
        chunks = DocumentProcessor.chunk_text(short_text)
        
        assert len(chunks) == 1
        assert chunks[0]['content'] == short_text
        assert chunks[0]['position'] == 0
        assert chunks[0]['overlap_start'] == 0
        assert chunks[0]['overlap_end'] == 0
    
    @patch('tiktoken.get_encoding')
    def test_chunk_text_multiple_chunks(self, mock_encoding):
        """Test chunking text that requires multiple chunks."""
        # Mock tokenizer
        mock_enc = MagicMock()
        # Simulate a text that would be 1500 tokens
        mock_enc.encode.side_effect = lambda text: list(range(len(text.split()) * 2))  # 2 tokens per word
        mock_enc.decode.side_effect = lambda tokens: ' '.join([f'word{i}' for i in range(len(tokens) // 2)])
        
        mock_encoding.return_value = mock_enc
        
        # Create text with ~750 words (1500 tokens)
        long_text = ' '.join([f'word{i}' for i in range(750)])
        
        chunks = DocumentProcessor.chunk_text(long_text, chunk_size=1000, overlap=200)
        
        assert len(chunks) > 1
        assert all(chunk['token_count'] <= 1000 for chunk in chunks)
        assert all(chunk['overlap_start'] == 200 for chunk in chunks[1:])  # All but first have overlap
        assert chunks[0]['overlap_start'] == 0  # First chunk has no start overlap
    
    def test_chunk_text_invalid_config(self):
        """Test error handling for invalid chunking configuration."""
        text = "Some text to chunk."
        
        with pytest.raises(ProcessingError, match="Overlap must be less than chunk size"):
            DocumentProcessor.chunk_text(text, chunk_size=100, overlap=150)
    
    def test_chunk_text_empty_text(self):
        """Test chunking empty text."""
        chunks = DocumentProcessor.chunk_text("")
        assert chunks == []
        
        chunks = DocumentProcessor.chunk_text("   ")
        assert chunks == []
    
    def test_count_tokens_with_tiktoken(self):
        """Test token counting with tiktoken."""
        text = "This is a test sentence with multiple words."
        
        # This will use the actual tiktoken if available
        token_count = DocumentProcessor._count_tokens(text)
        
        assert token_count > 0
        assert isinstance(token_count, int)
    
    @patch('tiktoken.get_encoding')
    def test_count_tokens_fallback(self, mock_encoding):
        """Test token counting fallback when tiktoken fails."""
        mock_encoding.side_effect = Exception("Tiktoken not available")
        
        text = "This is a test sentence with six words."
        token_count = DocumentProcessor._count_tokens(text)
        
        # Should fall back to word count * 1.3
        expected = int(7 * 1.3)  # 7 words
        assert token_count == expected
    
    def test_is_valid_url(self):
        """Test URL validation."""
        assert DocumentProcessor._is_valid_url("https://example.com")
        assert DocumentProcessor._is_valid_url("http://test.org/path")
        assert not DocumentProcessor._is_valid_url("not-a-url")
        assert not DocumentProcessor._is_valid_url("ftp://example.com")  # Only http/https
        assert not DocumentProcessor._is_valid_url("")
    
    def test_extract_title_from_url(self):
        """Test extracting title from URL."""
        assert DocumentProcessor._extract_title_from_url("https://example.com/my-article") == "My Article"
        assert DocumentProcessor._extract_title_from_url("https://example.com/test_page.html") == "Test Page"
        assert DocumentProcessor._extract_title_from_url("https://example.com/") == "example.com"
        assert DocumentProcessor._extract_title_from_url("https://example.com") == "example.com"
    
    def test_parse_html_content(self):
        """Test HTML content parsing."""
        html = """
        <html>
        <head>
            <title>Test Page</title>
            <meta name="description" content="Test description">
        </head>
        <body>
            <script>alert('remove me');</script>
            <style>body { color: red; }</style>
            <h1>Main Heading</h1>
            <p>First paragraph.</p>
            <p>Second paragraph.</p>
        </body>
        </html>
        """
        
        content, metadata = DocumentProcessor._parse_html_content(html)
        
        assert 'Main Heading' in content
        assert 'First paragraph.' in content
        assert 'Second paragraph.' in content
        assert 'alert' not in content  # Script removed
        assert 'color: red' not in content  # Style removed
        
        assert metadata['title'] == 'Test Page'
        assert metadata['description'] == 'Test description'
        assert metadata['format'] == 'html'