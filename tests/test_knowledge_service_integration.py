"""Integration tests for KnowledgeService with document processing pipeline."""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock
from werkzeug.datastructures import FileStorage
from io import BytesIO

from app.services.knowledge_service import KnowledgeService
from app.models.knowledge import KnowledgeSource, Document, Chunk
from app.utils.exceptions import ValidationError, ProcessingError


class TestKnowledgeServiceIntegration:
    """Integration test cases for KnowledgeService with document processing."""
    
    @pytest.fixture
    def mock_app_context(self):
        """Mock Flask application context."""
        with patch('flask.current_app') as mock_app:
            mock_app.config = {'UPLOAD_FOLDER': '/tmp/test_uploads'}
            mock_app.logger = MagicMock()
            yield mock_app
    
    @pytest.fixture
    def sample_knowledge_source(self):
        """Create a sample knowledge source for testing."""
        with patch.object(KnowledgeSource, 'create') as mock_create:
            source = MagicMock()
            source.id = 1
            source.tenant_id = 1
            source.name = "Test Source"
            source.source_type = "document"
            source.status = "pending"
            mock_create.return_value = source
            yield source
    
    @pytest.fixture
    def sample_url_source(self):
        """Create a sample URL knowledge source for testing."""
        with patch.object(KnowledgeSource, 'create_url_source') as mock_create:
            source = MagicMock()
            source.id = 2
            source.tenant_id = 1
            source.name = "Test URL Source"
            source.source_type = "url"
            source.source_url = "https://example.com"
            source.max_depth = 1
            source.status = "pending"
            mock_create.return_value = source
            yield source
    
    def test_create_document_source(self, mock_app_context):
        """Test creating a document-based knowledge source."""
        with patch.object(KnowledgeSource, 'create_document_source') as mock_create:
            mock_source = MagicMock()
            mock_source.save.return_value = None
            mock_create.return_value = mock_source
            
            result = KnowledgeService.create_document_source(
                tenant_id=1,
                name="Test Document Source",
                description="Test description",
                tags=["test", "document"]
            )
            
            assert result == mock_source
            mock_create.assert_called_once_with(
                tenant_id=1,
                name="Test Document Source",
                description="Test description",
                tags=["test", "document"]
            )
            mock_source.save.assert_called_once()
    
    def test_create_url_source_valid(self, mock_app_context):
        """Test creating a URL-based knowledge source with valid URL."""
        with patch.object(KnowledgeService, '_is_valid_url', return_value=True):
            with patch.object(KnowledgeSource, 'create_url_source') as mock_create:
                mock_source = MagicMock()
                mock_source.save.return_value = None
                mock_create.return_value = mock_source
                
                result = KnowledgeService.create_url_source(
                    tenant_id=1,
                    name="Test URL Source",
                    url="https://example.com",
                    description="Test description"
                )
                
                assert result == mock_source
                mock_create.assert_called_once()
                mock_source.save.assert_called_once()
    
    def test_create_url_source_invalid_url(self, mock_app_context):
        """Test creating URL source with invalid URL."""
        with patch.object(KnowledgeService, '_is_valid_url', return_value=False):
            with pytest.raises(ValidationError, match="Invalid URL format"):
                KnowledgeService.create_url_source(
                    tenant_id=1,
                    name="Test URL Source",
                    url="not-a-url"
                )
    
    @patch('app.services.knowledge_service.DocumentProcessor')
    @patch('app.services.knowledge_service.TextChunker')
    @patch('os.makedirs')
    @patch('os.path.getsize')
    def test_upload_document_success(self, mock_getsize, mock_makedirs, mock_chunker_class, 
                                   mock_processor, mock_app_context, sample_knowledge_source):
        """Test successful document upload and processing."""
        # Setup mocks
        mock_getsize.return_value = 1024
        
        # Mock DocumentProcessor
        mock_processor.extract_text_from_file.return_value = {
            'content': 'Test document content',
            'token_count': 10,
            'content_hash': 'abc123',
            'metadata': {'title': 'Test Document', 'format': 'plain_text'}
        }
        
        # Mock TextChunker
        mock_chunker = MagicMock()
        mock_chunker.chunk_document_content.return_value = [
            {
                'content': 'Test document content',
                'position': 0,
                'token_count': 10,
                'overlap_start': 0,
                'overlap_end': 0,
                'chunk_type': 'single',
                'is_first': True,
                'is_last': True
            }
        ]
        mock_chunker_class.return_value = mock_chunker
        
        # Mock file
        file_content = b"Test file content"
        file = FileStorage(
            stream=BytesIO(file_content),
            filename="test.txt",
            content_type="text/plain"
        )
        
        # Mock database operations
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_knowledge_source):
            with patch.object(Document, 'create') as mock_doc_create:
                with patch.object(Chunk, 'create') as mock_chunk_create:
                    mock_document = MagicMock()
                    mock_document.id = 1
                    mock_document.mark_as_processing.return_value = mock_document
                    mock_document.mark_as_completed.return_value = mock_document
                    mock_document.save.return_value = None
                    mock_doc_create.return_value = mock_document
                    
                    mock_chunk = MagicMock()
                    mock_chunk.save.return_value = None
                    mock_chunk_create.return_value = mock_chunk
                    
                    sample_knowledge_source.update_statistics.return_value = sample_knowledge_source
                    sample_knowledge_source.save.return_value = None
                    
                    # Test the upload
                    result = KnowledgeService.upload_document(
                        tenant_id=1,
                        source_id=1,
                        file=file,
                        title="Custom Title"
                    )
                    
                    # Assertions
                    assert result == mock_document
                    mock_processor.extract_text_from_file.assert_called_once()
                    mock_chunker.chunk_document_content.assert_called_once()
                    mock_doc_create.assert_called_once()
                    mock_chunk_create.assert_called_once()
                    mock_document.mark_as_processing.assert_called_once()
                    mock_document.mark_as_completed.assert_called_once()
                    sample_knowledge_source.update_statistics.assert_called_once()
    
    def test_upload_document_no_file(self, mock_app_context):
        """Test upload document with no file provided."""
        with pytest.raises(ValidationError, match="No file provided"):
            KnowledgeService.upload_document(tenant_id=1, source_id=1, file=None)
    
    def test_upload_document_invalid_file_type(self, mock_app_context):
        """Test upload document with invalid file type."""
        file = FileStorage(
            stream=BytesIO(b"content"),
            filename="test.exe",
            content_type="application/octet-stream"
        )
        
        with pytest.raises(ValidationError, match="File type not allowed"):
            KnowledgeService.upload_document(tenant_id=1, source_id=1, file=file)
    
    def test_upload_document_source_not_found(self, mock_app_context):
        """Test upload document with non-existent source."""
        file = FileStorage(
            stream=BytesIO(b"content"),
            filename="test.txt",
            content_type="text/plain"
        )
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=None):
            with pytest.raises(ValidationError, match="Knowledge source not found"):
                KnowledgeService.upload_document(tenant_id=1, source_id=999, file=file)
    
    def test_upload_document_wrong_source_type(self, mock_app_context):
        """Test upload document to URL source."""
        file = FileStorage(
            stream=BytesIO(b"content"),
            filename="test.txt",
            content_type="text/plain"
        )
        
        url_source = MagicMock()
        url_source.tenant_id = 1
        url_source.source_type = "url"
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=url_source):
            with pytest.raises(ValidationError, match="Source is not configured for document uploads"):
                KnowledgeService.upload_document(tenant_id=1, source_id=1, file=file)
    
    @patch('app.services.knowledge_service.WebScraper')
    @patch('app.services.knowledge_service.TextChunker')
    @patch('hashlib.sha256')
    def test_crawl_url_success(self, mock_sha256, mock_chunker_class, mock_scraper_class,
                              mock_app_context, sample_url_source):
        """Test successful URL crawling and processing."""
        # Setup mocks
        mock_hash = MagicMock()
        mock_hash.hexdigest.return_value = 'content_hash_123'
        mock_sha256.return_value = mock_hash
        
        # Mock WebScraper
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.__exit__.return_value = None
        mock_scraper.scrape_url.return_value = [
            {
                'content': 'Scraped web content',
                'title': 'Web Page Title',
                'url': 'https://example.com',
                'token_count': 15,
                'metadata': {'format': 'html'}
            }
        ]
        mock_scraper_class.return_value = mock_scraper
        
        # Mock TextChunker
        mock_chunker = MagicMock()
        mock_chunker.chunk_document_content.return_value = [
            {
                'content': 'Scraped web content',
                'position': 0,
                'token_count': 15,
                'overlap_start': 0,
                'overlap_end': 0,
                'chunk_type': 'single',
                'is_first': True,
                'is_last': True
            }
        ]
        mock_chunker_class.return_value = mock_chunker
        
        # Mock database operations
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_url_source):
            with patch.object(Document, 'find_by_content_hash', return_value=None):
                with patch.object(Document, 'create') as mock_doc_create:
                    with patch.object(Chunk, 'create') as mock_chunk_create:
                        mock_document = MagicMock()
                        mock_document.id = 1
                        mock_document.mark_as_processing.return_value = mock_document
                        mock_document.mark_as_completed.return_value = mock_document
                        mock_document.save.return_value = None
                        mock_doc_create.return_value = mock_document
                        
                        mock_chunk = MagicMock()
                        mock_chunk.save.return_value = None
                        mock_chunk_create.return_value = mock_chunk
                        
                        sample_url_source.mark_as_processing.return_value = sample_url_source
                        sample_url_source.mark_as_completed.return_value = sample_url_source
                        sample_url_source.update_statistics.return_value = sample_url_source
                        sample_url_source.save.return_value = None
                        
                        # Test the crawl
                        result = KnowledgeService.crawl_url(
                            tenant_id=1,
                            source_id=2,
                            url="https://example.com"
                        )
                        
                        # Assertions
                        assert len(result) == 1
                        assert result[0] == mock_document
                        mock_scraper.scrape_url.assert_called_once_with("https://example.com", max_depth=1)
                        mock_chunker.chunk_document_content.assert_called_once()
                        mock_doc_create.assert_called_once()
                        mock_chunk_create.assert_called_once()
                        sample_url_source.mark_as_processing.assert_called_once()
                        sample_url_source.mark_as_completed.assert_called_once()
    
    @patch('app.services.knowledge_service.WebScraper')
    def test_crawl_url_duplicate_content(self, mock_scraper_class, mock_app_context, sample_url_source):
        """Test URL crawling with duplicate content detection."""
        # Mock WebScraper
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.__exit__.return_value = None
        mock_scraper.scrape_url.return_value = [
            {
                'content': 'Duplicate content',
                'title': 'Duplicate Page',
                'url': 'https://example.com/duplicate',
                'token_count': 10,
                'metadata': {'format': 'html'}
            }
        ]
        mock_scraper_class.return_value = mock_scraper
        
        # Mock existing document
        existing_doc = MagicMock()
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_url_source):
            with patch('hashlib.sha256') as mock_sha256:
                mock_hash = MagicMock()
                mock_hash.hexdigest.return_value = 'duplicate_hash'
                mock_sha256.return_value = mock_hash
                
                with patch.object(Document, 'find_by_content_hash', return_value=existing_doc):
                    sample_url_source.mark_as_processing.return_value = sample_url_source
                    sample_url_source.mark_as_completed.return_value = sample_url_source
                    sample_url_source.update_statistics.return_value = sample_url_source
                    sample_url_source.save.return_value = None
                    
                    result = KnowledgeService.crawl_url(tenant_id=1, source_id=2)
                    
                    # Should return empty list since content was duplicate
                    assert result == []
    
    def test_crawl_url_source_not_found(self, mock_app_context):
        """Test crawling URL with non-existent source."""
        with patch.object(KnowledgeSource, 'get_by_id', return_value=None):
            with pytest.raises(ValidationError, match="Knowledge source not found"):
                KnowledgeService.crawl_url(tenant_id=1, source_id=999)
    
    def test_crawl_url_wrong_source_type(self, mock_app_context):
        """Test crawling URL with document source."""
        doc_source = MagicMock()
        doc_source.tenant_id = 1
        doc_source.source_type = "document"
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=doc_source):
            with pytest.raises(ValidationError, match="Source is not configured for URL crawling"):
                KnowledgeService.crawl_url(tenant_id=1, source_id=1)
    
    def test_crawl_url_no_url(self, mock_app_context, sample_url_source):
        """Test crawling URL source with no URL specified."""
        sample_url_source.source_url = None
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_url_source):
            with pytest.raises(ValidationError, match="No URL to crawl"):
                KnowledgeService.crawl_url(tenant_id=1, source_id=2)
    
    @patch('app.services.knowledge_service.WebScraper')
    def test_crawl_url_scraping_error(self, mock_scraper_class, mock_app_context, sample_url_source):
        """Test URL crawling with scraping error."""
        # Mock WebScraper to raise error
        mock_scraper = MagicMock()
        mock_scraper.__enter__.return_value = mock_scraper
        mock_scraper.__exit__.return_value = None
        mock_scraper.scrape_url.side_effect = Exception("Scraping failed")
        mock_scraper_class.return_value = mock_scraper
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_url_source):
            sample_url_source.mark_as_processing.return_value = sample_url_source
            sample_url_source.mark_as_error.return_value = sample_url_source
            sample_url_source.save.return_value = None
            
            with pytest.raises(Exception, match="Scraping failed"):
                KnowledgeService.crawl_url(tenant_id=1, source_id=2)
            
            # Should mark source as error
            sample_url_source.mark_as_error.assert_called_once_with("Scraping failed")
    
    def test_get_sources(self, mock_app_context):
        """Test getting knowledge sources."""
        mock_sources = [MagicMock(), MagicMock()]
        
        with patch.object(KnowledgeSource, 'query') as mock_query:
            mock_query.filter_by.return_value.order_by.return_value.all.return_value = mock_sources
            
            result = KnowledgeService.get_sources(tenant_id=1)
            
            assert result == mock_sources
            mock_query.filter_by.assert_called_once_with(tenant_id=1)
    
    def test_get_sources_with_status_filter(self, mock_app_context):
        """Test getting knowledge sources with status filter."""
        mock_sources = [MagicMock()]
        
        with patch.object(KnowledgeSource, 'query') as mock_query:
            mock_query.filter_by.return_value.filter_by.return_value.order_by.return_value.all.return_value = mock_sources
            
            result = KnowledgeService.get_sources(tenant_id=1, status='completed')
            
            assert result == mock_sources
    
    def test_get_source_documents(self, mock_app_context, sample_knowledge_source):
        """Test getting documents for a knowledge source."""
        mock_documents = [MagicMock(), MagicMock()]
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_knowledge_source):
            with patch.object(Document, 'get_by_source', return_value=mock_documents):
                result = KnowledgeService.get_source_documents(tenant_id=1, source_id=1)
                
                assert result == mock_documents
    
    def test_delete_source_success(self, mock_app_context, sample_knowledge_source):
        """Test successful source deletion."""
        # Mock documents with file paths
        mock_doc1 = MagicMock()
        mock_doc1.file_path = "/tmp/test1.txt"
        mock_doc2 = MagicMock()
        mock_doc2.file_path = "/tmp/test2.txt"
        
        sample_knowledge_source.documents = [mock_doc1, mock_doc2]
        sample_knowledge_source.delete.return_value = None
        
        with patch.object(KnowledgeSource, 'get_by_id', return_value=sample_knowledge_source):
            with patch('os.path.exists', return_value=True):
                with patch('os.remove') as mock_remove:
                    result = KnowledgeService.delete_source(tenant_id=1, source_id=1)
                    
                    assert result is True
                    assert mock_remove.call_count == 2
                    sample_knowledge_source.delete.assert_called_once()
    
    def test_delete_document_success(self, mock_app_context):
        """Test successful document deletion."""
        mock_document = MagicMock()
        mock_document.tenant_id = 1
        mock_document.file_path = "/tmp/test.txt"
        mock_document.delete.return_value = None
        
        mock_source = MagicMock()
        mock_source.update_statistics.return_value = mock_source
        mock_source.save.return_value = None
        mock_document.source = mock_source
        
        with patch.object(Document, 'get_by_id', return_value=mock_document):
            with patch('os.path.exists', return_value=True):
                with patch('os.remove') as mock_remove:
                    result = KnowledgeService.delete_document(tenant_id=1, document_id=1)
                    
                    assert result is True
                    mock_remove.assert_called_once_with("/tmp/test.txt")
                    mock_document.delete.assert_called_once()
                    mock_source.update_statistics.assert_called_once()
    
    def test_is_allowed_file(self):
        """Test file extension validation."""
        assert KnowledgeService._is_allowed_file("test.txt")
        assert KnowledgeService._is_allowed_file("document.pdf")
        assert KnowledgeService._is_allowed_file("page.html")
        assert KnowledgeService._is_allowed_file("readme.md")
        assert not KnowledgeService._is_allowed_file("script.exe")
        assert not KnowledgeService._is_allowed_file("image.jpg")
        assert not KnowledgeService._is_allowed_file("noextension")
    
    def test_is_valid_url(self):
        """Test URL validation."""
        assert KnowledgeService._is_valid_url("https://example.com")
        assert KnowledgeService._is_valid_url("http://test.org/path")
        assert not KnowledgeService._is_valid_url("not-a-url")
        assert not KnowledgeService._is_valid_url("ftp://example.com")
        assert not KnowledgeService._is_valid_url("")