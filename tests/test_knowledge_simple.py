"""Simple tests for knowledge management functionality."""
import os
import tempfile
import pytest
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.knowledge import KnowledgeSource, Document
from app.services.knowledge_service import KnowledgeService
from app.utils.exceptions import ValidationError, ProcessingError


class TestKnowledgeService:
    """Test knowledge service functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Create test app
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        self.app.config['DB_SCHEMA'] = None
        self.app.config['TESTING'] = True
        self.app.config['WTF_CSRF_ENABLED'] = False
        self.app.config['HEALTH_CHECK_DATABASE_ENABLED'] = False
        self.app.config['HEALTH_CHECK_REDIS_ENABLED'] = False
        self.app.config['TENANT_MIDDLEWARE_ENABLED'] = False
        
        with self.app.app_context():
            # Create all tables
            db.create_all()
            
            # Create test tenant
            self.tenant = Tenant(
                name="Test Tenant",
                domain="test.example.com",
                slug="test-tenant",
                settings={"test": True}
            )
            db.session.add(self.tenant)
            db.session.commit()
            
            yield
            
        # Cleanup
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_create_document_source(self):
        """Test creating a document source."""
        with self.app.app_context():
            source = KnowledgeService.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Documents",
                description="Test description",
                tags=["test", "documents"]
            )
            
            assert source.id is not None
            assert source.name == "Test Documents"
            assert source.source_type == "document"
            assert source.description == "Test description"
            assert "test" in source.tags
            assert source.status == "pending"
    
    def test_create_url_source(self):
        """Test creating a URL source."""
        with self.app.app_context():
            source = KnowledgeService.create_url_source(
                tenant_id=self.tenant.id,
                name="Test Website",
                url="https://example.com",
                description="Test URL source",
                crawl_frequency="weekly",
                max_depth=2
            )
            
            assert source.id is not None
            assert source.name == "Test Website"
            assert source.source_type == "url"
            assert source.source_url == "https://example.com"
            assert source.crawl_frequency == "weekly"
            assert source.max_depth == 2
    
    def test_create_url_source_invalid_url(self):
        """Test creating URL source with invalid URL."""
        with self.app.app_context():
            with pytest.raises(ValidationError) as exc_info:
                KnowledgeService.create_url_source(
                    tenant_id=self.tenant.id,
                    name="Test Website",
                    url="invalid-url"
                )
            
            assert "invalid url" in str(exc_info.value).lower()
    
    def test_get_sources(self):
        """Test getting knowledge sources."""
        with self.app.app_context():
            # Create test sources
            source1 = KnowledgeService.create_document_source(
                tenant_id=self.tenant.id,
                name="Source 1"
            )
            
            source2 = KnowledgeService.create_url_source(
                tenant_id=self.tenant.id,
                name="Source 2",
                url="https://example.com"
            )
            
            # Get all sources
            sources = KnowledgeService.get_sources(self.tenant.id)
            assert len(sources) == 2
            
            # Get sources by status
            pending_sources = KnowledgeService.get_sources(self.tenant.id, status="pending")
            assert len(pending_sources) == 2
            
            completed_sources = KnowledgeService.get_sources(self.tenant.id, status="completed")
            assert len(completed_sources) == 0
    
    def test_search_knowledge_empty(self):
        """Test searching empty knowledge base."""
        with self.app.app_context():
            results = KnowledgeService.search_knowledge(
                tenant_id=self.tenant.id,
                query="test query"
            )
            
            assert results == []
    
    def test_search_knowledge_with_documents(self):
        """Test searching knowledge base with documents."""
        with self.app.app_context():
            # Create source and documents
            source = KnowledgeService.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Documents"
            )
            source.mark_as_completed()
            source.save()
            
            # Create test documents
            doc1 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Python Programming Guide",
                content="Learn Python programming with examples and tutorials"
            )
            doc1.save()
            
            doc2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="JavaScript Tutorial",
                content="JavaScript basics and advanced concepts"
            )
            doc2.save()
            
            # Search for Python
            results = KnowledgeService.search_knowledge(
                tenant_id=self.tenant.id,
                query="Python programming",
                limit=10,
                min_similarity=0.1
            )
            
            assert len(results) >= 1
            assert results[0]['title'] == "Python Programming Guide"
            assert results[0]['relevance_score'] > 0
            assert 'citations' in results[0]
    
    def test_delete_source(self):
        """Test deleting a knowledge source."""
        with self.app.app_context():
            # Create source
            source = KnowledgeService.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Source"
            )
            source_id = source.id
            
            # Delete source
            success = KnowledgeService.delete_source(self.tenant.id, source_id)
            assert success is True
            
            # Verify source is deleted
            deleted_source = KnowledgeSource.get_by_id(source_id)
            assert deleted_source is None
    
    def test_delete_nonexistent_source(self):
        """Test deleting a non-existent source."""
        with self.app.app_context():
            with pytest.raises(ValidationError) as exc_info:
                KnowledgeService.delete_source(self.tenant.id, 99999)
            
            assert "not found" in str(exc_info.value).lower()
    
    def test_get_source_documents(self):
        """Test getting documents for a source."""
        with self.app.app_context():
            # Create source and documents
            source = KnowledgeService.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Documents"
            )
            
            doc1 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Document 1",
                content="Content 1"
            )
            doc1.save()
            
            doc2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Document 2",
                content="Content 2"
            )
            doc2.save()
            
            # Get documents
            documents = KnowledgeService.get_source_documents(self.tenant.id, source.id)
            assert len(documents) == 2
            
            titles = [doc.title for doc in documents]
            assert "Document 1" in titles
            assert "Document 2" in titles
    
    def test_delete_document(self):
        """Test deleting a document."""
        with self.app.app_context():
            # Create source and document
            source = KnowledgeService.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Documents"
            )
            
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Test Document",
                content="Test content"
            )
            document.save()
            document_id = document.id
            
            # Delete document
            success = KnowledgeService.delete_document(self.tenant.id, document_id)
            assert success is True
            
            # Verify document is deleted
            deleted_document = Document.get_by_id(document_id)
            assert deleted_document is None


class TestKnowledgeModels:
    """Test knowledge models functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test environment."""
        # Create temporary database
        self.db_fd, self.db_path = tempfile.mkstemp()
        
        # Create test app
        self.app = create_app('testing')
        self.app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{self.db_path}'
        self.app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
        self.app.config['DB_SCHEMA'] = None
        self.app.config['TESTING'] = True
        
        with self.app.app_context():
            # Create all tables
            db.create_all()
            
            # Create test tenant
            self.tenant = Tenant(
                name="Test Tenant",
                domain="test.example.com",
                slug="test-tenant",
                settings={"test": True}
            )
            db.session.add(self.tenant)
            db.session.commit()
            
            yield
            
        # Cleanup
        os.close(self.db_fd)
        os.unlink(self.db_path)
    
    def test_knowledge_source_creation(self):
        """Test KnowledgeSource model creation."""
        with self.app.app_context():
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Source",
                description="Test description"
            )
            source.save()
            
            assert source.id is not None
            assert source.tenant_id == self.tenant.id
            assert source.name == "Test Source"
            assert source.source_type == "document"
            assert source.status == "pending"
    
    def test_knowledge_source_status_methods(self):
        """Test KnowledgeSource status methods."""
        with self.app.app_context():
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Source"
            )
            source.save()
            
            # Test mark as processing
            source.mark_as_processing()
            assert source.status == "processing"
            assert source.last_error is None
            
            # Test mark as completed
            source.mark_as_completed()
            assert source.status == "completed"
            assert source.last_crawled_at is not None
            
            # Test mark as error
            source.mark_as_error("Test error")
            assert source.status == "error"
            assert source.last_error == "Test error"
    
    def test_knowledge_source_tags(self):
        """Test KnowledgeSource tag methods."""
        with self.app.app_context():
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Source"
            )
            source.save()
            
            # Add tags
            source.add_tag("test")
            source.add_tag("documents")
            assert source.has_tag("test")
            assert source.has_tag("documents")
            assert not source.has_tag("nonexistent")
            
            # Remove tag
            source.remove_tag("test")
            assert not source.has_tag("test")
            assert source.has_tag("documents")
    
    def test_document_creation(self):
        """Test Document model creation."""
        with self.app.app_context():
            # Create source first
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Source"
            )
            source.save()
            
            # Create document
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Test Document",
                content="Test content",
                filename="test.txt",
                mime_type="text/plain"
            )
            document.save()
            
            assert document.id is not None
            assert document.tenant_id == self.tenant.id
            assert document.source_id == source.id
            assert document.title == "Test Document"
            assert document.content == "Test content"
            assert document.filename == "test.txt"
            assert document.mime_type == "text/plain"
    
    def test_document_content_hash(self):
        """Test Document content hash generation."""
        with self.app.app_context():
            # Create source first
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name="Test Source"
            )
            source.save()
            
            # Create document
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Test Document",
                content="Test content"
            )
            document.generate_content_hash()
            document.save()
            
            assert document.content_hash is not None
            assert len(document.content_hash) == 64  # SHA-256 hex length
            
            # Create another document with same content
            document2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title="Test Document 2",
                content="Test content"
            )
            document2.generate_content_hash()
            
            assert document.content_hash == document2.content_hash