"""Test knowledge management models."""
import pytest
import numpy as np
from datetime import datetime
from app.models.tenant import Tenant
from app.models.user import User
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app import db


class TestKnowledgeSource:
    """Test KnowledgeSource model."""
    
    def test_create_knowledge_source(self, app):
        """Test knowledge source creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Company Docs",
                description="Internal company documentation",
                source_type="document"
            )
            source.save()
            
            assert source.id is not None
            assert source.name == "Company Docs"
            assert source.source_type == "document"
            assert source.status == "pending"
            assert source.document_count == 0
    
    def test_knowledge_source_metadata_and_tags(self, app):
        """Test knowledge source metadata and tags."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="url"
            )
            source.save()
            
            # Test metadata
            source.set_metadata("last_update", "2024-01-01")
            source.set_metadata("priority", "high")
            source.save()
            
            assert source.get_metadata("last_update") == "2024-01-01"
            assert source.get_metadata("priority") == "high"
            assert source.get_metadata("nonexistent") is None
            
            # Test tags
            source.add_tag("important")
            source.add_tag("public")
            source.save()
            
            assert source.has_tag("important")
            assert source.has_tag("public")
            assert len(source.tags) == 2
            
            source.remove_tag("important")
            source.save()
            
            assert not source.has_tag("important")
            assert source.has_tag("public")
    
    def test_knowledge_source_status_management(self, app):
        """Test knowledge source status management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            # Test marking as processing
            source.mark_as_processing()
            source.save()
            
            assert source.status == "processing"
            assert source.last_error is None
            
            # Test marking as completed
            source.mark_as_completed()
            source.save()
            
            assert source.status == "completed"
            assert source.last_crawled_at is not None
            assert source.last_error is None
            
            # Test marking as error
            source.mark_as_error("Connection failed")
            source.save()
            
            assert source.status == "error"
            assert source.last_error == "Connection failed"
    
    def test_create_specific_source_types(self, app):
        """Test creating specific source types."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Test document source
            doc_source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name="PDF Documents"
            )
            
            assert doc_source.source_type == "document"
            assert doc_source.source_url is None
            
            # Test URL source
            url_source = KnowledgeSource.create_url_source(
                tenant_id=tenant.id,
                name="Company Website",
                url="https://example.com"
            )
            
            assert url_source.source_type == "url"
            assert url_source.source_url == "https://example.com"


class TestDocument:
    """Test Document model."""
    
    def test_create_document(self, app):
        """Test document creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            document = Document(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document",
                content="This is a test document with some content.",
                filename="test.txt",
                mime_type="text/plain"
            )
            document.save()
            
            assert document.id is not None
            assert document.title == "Test Document"
            assert document.source_id == source.id
            assert document.processing_status == "pending"
    
    def test_document_content_hash(self, app):
        """Test document content hash generation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            document = Document(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document",
                content="This is test content for hashing."
            )
            document.generate_content_hash()
            document.save()
            
            assert document.content_hash is not None
            assert len(document.content_hash) == 64  # SHA-256 hash length
            
            # Test finding by content hash
            found_doc = Document.find_by_content_hash(tenant.id, document.content_hash)
            assert found_doc.id == document.id
    
    def test_document_status_management(self, app):
        """Test document status management."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            document = Document(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document"
            )
            document.save()
            
            # Test marking as processing
            document.mark_as_processing()
            document.save()
            
            assert document.processing_status == "processing"
            
            # Test marking as completed
            document.mark_as_completed()
            document.save()
            
            assert document.processing_status == "completed"
            
            # Test marking as error
            document.mark_as_error()
            document.save()
            
            assert document.processing_status == "error"


class TestChunk:
    """Test Chunk model."""
    
    def test_create_chunk(self, app):
        """Test chunk creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            document = Document(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document",
                content="This is a long document that will be chunked."
            )
            document.save()
            
            chunk = Chunk(
                tenant_id=tenant.id,
                document_id=document.id,
                content="This is a chunk of the document.",
                position=0,
                token_count=8
            )
            chunk.save()
            
            assert chunk.id is not None
            assert chunk.document_id == document.id
            assert chunk.position == 0
            assert chunk.token_count == 8
    
    def test_chunk_content_preview(self, app):
        """Test chunk content preview."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Create a chunk with long content
            long_content = "This is a very long piece of content that should be truncated when generating a preview. " * 10
            
            chunk = Chunk(
                tenant_id=tenant.id,
                content=long_content,
                position=0
            )
            
            preview = chunk.get_content_preview(100)
            assert len(preview) <= 103  # 100 + "..."
            assert preview.endswith("...")
            
            # Test short content
            short_content = "Short content"
            chunk.content = short_content
            
            preview = chunk.get_content_preview(100)
            assert preview == short_content
            assert not preview.endswith("...")


class TestEmbedding:
    """Test Embedding model."""
    
    def test_create_embedding(self, app):
        """Test embedding creation."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            document = Document(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document"
            )
            document.save()
            
            chunk = Chunk(
                tenant_id=tenant.id,
                document_id=document.id,
                content="Test chunk content",
                position=0
            )
            chunk.save()
            
            # Create test vector
            test_vector = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
            
            embedding = Embedding.create_from_vector(
                tenant_id=tenant.id,
                chunk_id=chunk.id,
                vector=test_vector,
                model_name="text-embedding-ada-002"
            )
            
            assert embedding.id is not None
            assert embedding.chunk_id == chunk.id
            assert embedding.model_name == "text-embedding-ada-002"
            assert embedding.dimension == 5
    
    def test_embedding_vector_operations(self, app):
        """Test embedding vector operations."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            chunk = Chunk(
                tenant_id=tenant.id,
                content="Test content",
                position=0
            )
            chunk.save()
            
            # Create embedding with vector
            test_vector = np.array([1.0, 0.0, 0.0])
            
            embedding = Embedding(
                tenant_id=tenant.id,
                chunk_id=chunk.id,
                model_name="test-model"
            )
            embedding.set_vector(test_vector)
            embedding.save()
            
            # Test getting vector back
            retrieved_vector = embedding.get_vector()
            np.testing.assert_array_equal(retrieved_vector, test_vector)
            
            # Test similarity calculation
            similar_vector = np.array([0.8, 0.6, 0.0])  # Should have high similarity
            similarity = embedding.calculate_similarity(similar_vector)
            assert similarity > 0.5  # Should be reasonably similar
            
            orthogonal_vector = np.array([0.0, 1.0, 0.0])  # Should have low similarity
            similarity = embedding.calculate_similarity(orthogonal_vector)
            assert similarity < 0.1  # Should be very different
    
    def test_find_similar_embeddings(self, app):
        """Test finding similar embeddings."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            # Create multiple chunks and embeddings
            vectors = [
                np.array([1.0, 0.0, 0.0]),  # Similar to query
                np.array([0.9, 0.1, 0.0]),  # Very similar to query
                np.array([0.0, 1.0, 0.0]),  # Different from query
                np.array([0.0, 0.0, 1.0])   # Different from query
            ]
            
            embeddings = []
            for i, vector in enumerate(vectors):
                chunk = Chunk(
                    tenant_id=tenant.id,
                    content=f"Test content {i}",
                    position=i
                )
                chunk.save()
                
                embedding = Embedding.create_from_vector(
                    tenant_id=tenant.id,
                    chunk_id=chunk.id,
                    vector=vector,
                    model_name="test-model"
                )
                embeddings.append(embedding)
            
            # Query with similar vector
            query_vector = np.array([0.95, 0.05, 0.0])
            
            similar = Embedding.find_similar(
                tenant_id=tenant.id,
                query_vector=query_vector,
                model_name="test-model",
                limit=2,
                min_similarity=0.8
            )
            
            # Should find the 2 most similar embeddings
            assert len(similar) == 2
            assert similar[0][1] > similar[1][1]  # First should be more similar
            assert similar[0][1] > 0.8  # Should meet minimum similarity


class TestKnowledgeIntegration:
    """Test knowledge model integration."""
    
    def test_knowledge_source_statistics_update(self, app):
        """Test updating knowledge source statistics."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            # Create documents with chunks
            for i in range(3):
                document = Document(
                    tenant_id=tenant.id,
                    source_id=source.id,
                    title=f"Document {i}",
                    token_count=100
                )
                document.save()
                
                # Create chunks for each document
                for j in range(2):
                    chunk = Chunk(
                        tenant_id=tenant.id,
                        document_id=document.id,
                        content=f"Chunk {j} of document {i}",
                        position=j
                    )
                    chunk.save()
            
            # Update statistics
            source.update_statistics()
            source.save()
            
            assert source.document_count == 3
            assert source.chunk_count == 6  # 3 documents * 2 chunks each
            assert source.total_tokens == 300  # 3 documents * 100 tokens each
    
    def test_document_chunk_relationship(self, app):
        """Test document-chunk relationships."""
        with app.app_context():
            tenant = Tenant(name="Test", slug="test")
            tenant.save()
            
            source = KnowledgeSource(
                tenant_id=tenant.id,
                name="Test Source",
                source_type="document"
            )
            source.save()
            
            document = Document(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document"
            )
            document.save()
            
            # Create chunks
            chunks = []
            for i in range(5):
                chunk = Chunk(
                    tenant_id=tenant.id,
                    document_id=document.id,
                    content=f"This is chunk {i}",
                    position=i
                )
                chunk.save()
                chunks.append(chunk)
            
            # Test document chunk count
            assert document.get_chunk_count() == 5
            
            # Test getting chunks by document
            retrieved_chunks = Chunk.get_by_document(document.id)
            assert len(retrieved_chunks) == 5
            assert retrieved_chunks[0].position == 0
            assert retrieved_chunks[-1].position == 4