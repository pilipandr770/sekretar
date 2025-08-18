"""Tests for embedding service functionality."""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from app.services.embedding_service import EmbeddingService
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app.utils.exceptions import ProcessingError


class TestEmbeddingService:
    """Test cases for EmbeddingService."""
    
    @pytest.fixture
    def embedding_service(self, app):
        """Create embedding service instance."""
        with app.app_context():
            with patch('app.services.embedding_service.current_app') as mock_app:
                mock_app.config.get.return_value = 'test-api-key'
                service = EmbeddingService()
                service.client = Mock()
                return service
    
    @pytest.fixture
    def sample_embedding_vector(self):
        """Create sample embedding vector."""
        return np.random.rand(1536).astype(np.float32)
    
    @pytest.fixture
    def mock_openai_response(self, sample_embedding_vector):
        """Create mock OpenAI API response."""
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].embedding = sample_embedding_vector.tolist()
        return mock_response
    
    def test_initialize_client_success(self, app):
        """Test successful OpenAI client initialization."""
        with app.app_context():
            with patch('app.services.embedding_service.current_app') as mock_app:
                mock_app.config.get.return_value = 'test-api-key'
                
                with patch('app.services.embedding_service.OpenAI') as mock_openai:
                    service = EmbeddingService()
                    
                    mock_openai.assert_called_once_with(api_key='test-api-key')
                    assert service.client is not None
    
    def test_initialize_client_no_api_key(self, app):
        """Test client initialization without API key."""
        with app.app_context():
            with patch('app.services.embedding_service.current_app') as mock_app:
                mock_app.config.get.return_value = None
                
                with pytest.raises(ProcessingError, match="OpenAI API key not configured"):
                    EmbeddingService()
    
    def test_generate_embedding_success(self, embedding_service, mock_openai_response, sample_embedding_vector):
        """Test successful embedding generation."""
        embedding_service.client.embeddings.create.return_value = mock_openai_response
        
        result = embedding_service.generate_embedding("test text")
        
        embedding_service.client.embeddings.create.assert_called_once_with(
            input="test text",
            model="text-embedding-ada-002"
        )
        
        assert isinstance(result, np.ndarray)
        assert len(result) == 1536
        np.testing.assert_array_equal(result, sample_embedding_vector)
    
    def test_generate_embedding_empty_text(self, embedding_service):
        """Test embedding generation with empty text."""
        with pytest.raises(ProcessingError, match="Empty text provided for embedding"):
            embedding_service.generate_embedding("")
    
    def test_generate_embedding_api_error(self, embedding_service):
        """Test embedding generation with API error."""
        embedding_service.client.embeddings.create.side_effect = Exception("API Error")
        
        with pytest.raises(ProcessingError, match="Failed to generate embedding"):
            embedding_service.generate_embedding("test text")
    
    def test_generate_embeddings_batch_success(self, embedding_service, sample_embedding_vector):
        """Test successful batch embedding generation."""
        mock_response = Mock()
        mock_response.data = [
            Mock(embedding=sample_embedding_vector.tolist()),
            Mock(embedding=sample_embedding_vector.tolist())
        ]
        embedding_service.client.embeddings.create.return_value = mock_response
        
        texts = ["text 1", "text 2"]
        results = embedding_service.generate_embeddings_batch(texts)
        
        assert len(results) == 2
        for result in results:
            assert isinstance(result, np.ndarray)
            assert len(result) == 1536
    
    def test_generate_embeddings_batch_with_empty_texts(self, embedding_service, sample_embedding_vector):
        """Test batch embedding generation with some empty texts."""
        mock_response = Mock()
        mock_response.data = [Mock(embedding=sample_embedding_vector.tolist())]
        embedding_service.client.embeddings.create.return_value = mock_response
        
        texts = ["text 1", "", "text 3"]
        results = embedding_service.generate_embeddings_batch(texts)
        
        assert len(results) == 3
        assert results[0].size > 0  # Valid embedding
        assert results[1].size == 0  # Empty embedding for empty text
        assert results[2].size > 0  # Valid embedding
    
    def test_create_chunk_embedding_success(self, embedding_service, sample_embedding_vector):
        """Test successful chunk embedding creation."""
        # Mock chunk
        mock_chunk = Mock()
        mock_chunk.id = 1
        mock_chunk.tenant_id = 1
        mock_chunk.content = "test content"
        
        with patch('app.models.knowledge.Chunk.get_by_id', return_value=mock_chunk):
            with patch('app.models.knowledge.Embedding.query') as mock_query:
                mock_query.filter_by.return_value.first.return_value = None  # No existing embedding
                
                with patch('app.models.knowledge.Embedding.create_from_vector') as mock_create:
                    mock_embedding = Mock()
                    mock_create.return_value = mock_embedding
                    
                    embedding_service.generate_embedding = Mock(return_value=sample_embedding_vector)
                    
                    result = embedding_service.create_chunk_embedding(1, 1)
                    
                    assert result == mock_embedding
                    mock_create.assert_called_once()
    
    def test_create_chunk_embedding_chunk_not_found(self, embedding_service):
        """Test chunk embedding creation with non-existent chunk."""
        with patch('app.models.knowledge.Chunk.get_by_id', return_value=None):
            with pytest.raises(ProcessingError, match="Chunk not found"):
                embedding_service.create_chunk_embedding(1, 999)
    
    def test_create_chunk_embedding_already_exists(self, embedding_service):
        """Test chunk embedding creation when embedding already exists."""
        mock_chunk = Mock()
        mock_chunk.id = 1
        mock_chunk.tenant_id = 1
        
        mock_embedding = Mock()
        
        with patch('app.models.knowledge.Chunk.get_by_id', return_value=mock_chunk):
            with patch('app.models.knowledge.Embedding.query') as mock_query:
                mock_query.filter_by.return_value.first.return_value = mock_embedding
                
                result = embedding_service.create_chunk_embedding(1, 1)
                
                assert result == mock_embedding
    
    def test_create_document_embeddings_success(self, embedding_service, sample_embedding_vector):
        """Test successful document embeddings creation."""
        # Mock document
        mock_document = Mock()
        mock_document.id = 1
        mock_document.tenant_id = 1
        
        # Mock chunks
        mock_chunks = [Mock(id=1, content="chunk 1"), Mock(id=2, content="chunk 2")]
        
        with patch('app.models.knowledge.Document.get_by_id', return_value=mock_document):
            with patch('app.models.knowledge.Chunk.get_by_document', return_value=mock_chunks):
                with patch('app.models.knowledge.Embedding.query') as mock_query:
                    mock_query.filter_by.return_value.filter.return_value.all.return_value = []
                    
                    embedding_service.generate_embeddings_batch = Mock(
                        return_value=[sample_embedding_vector, sample_embedding_vector]
                    )
                    
                    with patch('app.models.knowledge.Embedding.create_from_vector') as mock_create:
                        mock_embeddings = [Mock(), Mock()]
                        mock_create.side_effect = mock_embeddings
                        
                        result = embedding_service.create_document_embeddings(1, 1)
                        
                        assert len(result) == 2
                        assert mock_create.call_count == 2
    
    def test_create_document_embeddings_document_not_found(self, embedding_service):
        """Test document embeddings creation with non-existent document."""
        with patch('app.models.knowledge.Document.get_by_id', return_value=None):
            with pytest.raises(ProcessingError, match="Document not found"):
                embedding_service.create_document_embeddings(1, 999)
    
    def test_create_document_embeddings_no_chunks(self, embedding_service):
        """Test document embeddings creation with no chunks."""
        mock_document = Mock()
        mock_document.id = 1
        mock_document.tenant_id = 1
        
        with patch('app.models.knowledge.Document.get_by_id', return_value=mock_document):
            with patch('app.models.knowledge.Chunk.get_by_document', return_value=[]):
                result = embedding_service.create_document_embeddings(1, 1)
                assert result == []
    
    def test_search_similar_chunks_success(self, embedding_service, sample_embedding_vector):
        """Test successful similar chunks search."""
        # Mock embeddings
        mock_chunk = Mock()
        mock_chunk.id = 1
        mock_chunk.content = "test content"
        mock_chunk.position = 0
        mock_chunk.token_count = 10
        
        mock_document = Mock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.url = "http://example.com"
        mock_document.source = Mock()
        mock_document.source.id = 1
        mock_document.source.name = "Test Source"
        mock_document.source.source_type = "url"
        mock_document.source.source_url = "http://example.com"
        
        mock_chunk.document = mock_document
        
        mock_embedding = Mock()
        mock_embedding.id = 1
        mock_embedding.chunk = mock_chunk
        mock_embedding.get_vector.return_value = sample_embedding_vector
        
        with patch('app.models.knowledge.Embedding.query') as mock_query:
            mock_query.join.return_value.filter.return_value.all.return_value = [mock_embedding]
            
            embedding_service.generate_embedding = Mock(return_value=sample_embedding_vector)
            embedding_service._calculate_cosine_similarity = Mock(return_value=0.9)
            
            results = embedding_service.search_similar_chunks(1, "test query")
            
            assert len(results) == 1
            result = results[0]
            assert result['chunk_id'] == 1
            assert result['document_id'] == 1
            assert result['similarity_score'] == 0.9
            assert 'citations' in result
            assert 'metadata' in result
    
    def test_search_similar_chunks_no_embeddings(self, embedding_service):
        """Test similar chunks search with no embeddings."""
        with patch('app.models.knowledge.Embedding.query') as mock_query:
            mock_query.join.return_value.filter.return_value.all.return_value = []
            
            embedding_service.generate_embedding = Mock(return_value=np.array([1, 2, 3]))
            
            results = embedding_service.search_similar_chunks(1, "test query")
            assert results == []
    
    def test_search_similar_chunks_low_similarity(self, embedding_service, sample_embedding_vector):
        """Test similar chunks search with low similarity scores."""
        mock_embedding = Mock()
        mock_embedding.get_vector.return_value = sample_embedding_vector
        mock_embedding.chunk = Mock()
        
        with patch('app.models.knowledge.Embedding.query') as mock_query:
            mock_query.join.return_value.filter.return_value.all.return_value = [mock_embedding]
            
            embedding_service.generate_embedding = Mock(return_value=sample_embedding_vector)
            embedding_service._calculate_cosine_similarity = Mock(return_value=0.5)  # Below threshold
            
            results = embedding_service.search_similar_chunks(1, "test query", min_similarity=0.7)
            assert results == []
    
    def test_reindex_knowledge_source_success(self, embedding_service):
        """Test successful knowledge source re-indexing."""
        # Mock source
        mock_source = Mock()
        mock_source.id = 1
        mock_source.tenant_id = 1
        
        # Mock documents
        mock_documents = [Mock(id=1), Mock(id=2)]
        
        with patch('app.models.knowledge.KnowledgeSource.get_by_id', return_value=mock_source):
            with patch('app.models.knowledge.Document.get_by_source', return_value=mock_documents):
                with patch('app.models.knowledge.Embedding.query') as mock_query:
                    mock_query.join.return_value.filter.return_value.all.return_value = []
                    
                    embedding_service.create_document_embeddings = Mock(
                        side_effect=[[Mock(), Mock()], [Mock()]]  # 2 embeddings for doc1, 1 for doc2
                    )
                    
                    result = embedding_service.reindex_knowledge_source(1, 1)
                    
                    assert result['source_id'] == 1
                    assert result['documents_processed'] == 2
                    assert result['embeddings_created'] == 3
                    assert result['embeddings_updated'] == 0
    
    def test_reindex_knowledge_source_not_found(self, embedding_service):
        """Test knowledge source re-indexing with non-existent source."""
        with patch('app.models.knowledge.KnowledgeSource.get_by_id', return_value=None):
            with pytest.raises(ProcessingError, match="Knowledge source not found"):
                embedding_service.reindex_knowledge_source(1, 999)
    
    def test_prepare_text(self, embedding_service):
        """Test text preparation for embedding."""
        # Test basic cleaning
        text = "  This is   a test   text  "
        result = embedding_service._prepare_text(text)
        assert result == "This is a test text"
        
        # Test empty text
        assert embedding_service._prepare_text("") == ""
        assert embedding_service._prepare_text(None) == ""
        
        # Test long text truncation
        long_text = " ".join(["word"] * 10000)
        result = embedding_service._prepare_text(long_text)
        assert len(result.split()) <= 8000
    
    def test_calculate_cosine_similarity(self, embedding_service):
        """Test cosine similarity calculation."""
        # Test identical vectors
        v1 = np.array([1, 0, 0])
        v2 = np.array([1, 0, 0])
        similarity = embedding_service._calculate_cosine_similarity(v1, v2)
        assert abs(similarity - 1.0) < 1e-6
        
        # Test orthogonal vectors
        v1 = np.array([1, 0, 0])
        v2 = np.array([0, 1, 0])
        similarity = embedding_service._calculate_cosine_similarity(v1, v2)
        assert abs(similarity - 0.0) < 1e-6
        
        # Test opposite vectors
        v1 = np.array([1, 0, 0])
        v2 = np.array([-1, 0, 0])
        similarity = embedding_service._calculate_cosine_similarity(v1, v2)
        assert abs(similarity - (-1.0)) < 1e-6
        
        # Test zero vectors
        v1 = np.array([0, 0, 0])
        v2 = np.array([1, 0, 0])
        similarity = embedding_service._calculate_cosine_similarity(v1, v2)
        assert similarity == 0.0
    
    def test_generate_citations(self, embedding_service):
        """Test citation generation."""
        # Mock chunk and document
        mock_chunk = Mock()
        mock_chunk.id = 1
        mock_chunk.position = 0
        
        mock_document = Mock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.url = "http://example.com"
        
        mock_source = Mock()
        mock_source.id = 1
        mock_source.name = "Test Source"
        mock_source.source_type = "url"
        mock_source.source_url = "http://example.com"
        
        mock_document.source = mock_source
        
        citations = embedding_service._generate_citations(mock_chunk, mock_document)
        
        assert citations['chunk_id'] == 1
        assert citations['position'] == 0
        assert citations['document_id'] == 1
        assert citations['document_title'] == "Test Document"
        assert citations['source_id'] == 1
        assert citations['source_name'] == "Test Source"
    
    def test_get_embedding_stats_success(self, app):
        """Test successful embedding statistics retrieval."""
        with app.app_context():
            with patch('app.models.knowledge.Embedding.query') as mock_embedding_query:
                with patch('app.models.knowledge.Chunk.query') as mock_chunk_query:
                    # Mock embedding stats
                    mock_embedding_query.filter_by.return_value.with_entities.return_value.group_by.return_value.all.return_value = [
                        ('text-embedding-ada-002', 10),
                        ('text-embedding-3-small', 5)
                    ]
                    
                    # Mock chunk stats
                    mock_chunk_query.filter_by.return_value.count.return_value = 20
                    mock_chunk_query.join.return_value.filter.return_value.distinct.return_value.count.return_value = 15
                    
                    stats = EmbeddingService.get_embedding_stats(1)
                    
                    assert stats['total_embeddings'] == 15
                    assert stats['embeddings_by_model']['text-embedding-ada-002'] == 10
                    assert stats['embeddings_by_model']['text-embedding-3-small'] == 5
                    assert stats['total_chunks'] == 20
                    assert stats['embedded_chunks'] == 15
                    assert stats['embedding_coverage'] == 75.0
    
    def test_get_embedding_stats_error(self, app):
        """Test embedding statistics retrieval with error."""
        with app.app_context():
            with patch('app.models.knowledge.Embedding.query') as mock_query:
                mock_query.filter_by.side_effect = Exception("Database error")
                
                stats = EmbeddingService.get_embedding_stats(1)
                
                assert 'error' in stats
                assert stats['total_embeddings'] == 0
                assert stats['embedding_coverage'] == 0
    
    def test_get_supported_models(self, embedding_service):
        """Test getting supported models."""
        models = embedding_service.get_supported_models()
        
        assert isinstance(models, dict)
        assert "text-embedding-ada-002" in models
        assert models["text-embedding-ada-002"] == 1536
    
    def test_validate_model(self, embedding_service):
        """Test model validation."""
        assert embedding_service.validate_model("text-embedding-ada-002") is True
        assert embedding_service.validate_model("text-embedding-3-small") is True
        assert embedding_service.validate_model("invalid-model") is False
    
    def test_get_model_dimension(self, embedding_service):
        """Test getting model dimensions."""
        assert embedding_service.get_model_dimension("text-embedding-ada-002") == 1536
        assert embedding_service.get_model_dimension("text-embedding-3-large") == 3072
        assert embedding_service.get_model_dimension("invalid-model") == 1536  # Default
    
    def test_enhanced_search_with_source_filter(self, embedding_service, sample_embedding_vector):
        """Test enhanced search with source filtering."""
        # Mock embeddings with different sources
        mock_chunk = Mock()
        mock_chunk.id = 1
        mock_chunk.content = "test content"
        mock_chunk.position = 0
        mock_chunk.token_count = 10
        mock_chunk.overlap_start = 0
        mock_chunk.overlap_end = 0
        mock_chunk.get_content_preview.return_value = "test content preview"
        mock_chunk.get_metadata.return_value = "text"
        
        mock_document = Mock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.url = "http://example.com"
        mock_document.source_id = 1
        mock_document.source = Mock()
        mock_document.source.id = 1
        mock_document.source.name = "Test Source"
        mock_document.source.source_type = "url"
        mock_document.source.source_url = "http://example.com"
        
        mock_chunk.document = mock_document
        
        mock_embedding = Mock()
        mock_embedding.id = 1
        mock_embedding.chunk = mock_chunk
        mock_embedding.get_vector.return_value = sample_embedding_vector
        
        with patch('app.models.knowledge.Embedding.query') as mock_query:
            mock_query.join.return_value.filter.return_value.join.return_value.filter.return_value.all.return_value = [mock_embedding]
            
            embedding_service.generate_embedding = Mock(return_value=sample_embedding_vector)
            embedding_service._calculate_cosine_similarity = Mock(return_value=0.9)
            embedding_service._calculate_relevance_score = Mock(return_value=0.85)
            embedding_service._generate_enhanced_citations = Mock(return_value={'test': 'citation'})
            
            results = embedding_service.search_similar_chunks(
                tenant_id=1, 
                query="test query", 
                source_ids=[1]
            )
            
            assert len(results) == 1
            result = results[0]
            assert result['chunk_id'] == 1
            assert result['similarity_score'] == 0.9
            assert result['relevance_score'] == 0.85
            assert 'content_preview' in result
            assert 'citations' in result
    
    def test_calculate_relevance_score(self, embedding_service):
        """Test relevance score calculation."""
        mock_chunk = Mock()
        mock_chunk.content = "This is a test document about machine learning"
        
        mock_document = Mock()
        mock_document.title = "Machine Learning Guide"
        mock_document.created_at = datetime.utcnow()
        
        query_terms = {"machine", "learning"}
        
        # Test with good matches
        score = embedding_service._calculate_relevance_score(0.8, mock_chunk, mock_document, query_terms)
        assert 0.8 <= score <= 1.0
        
        # Test with no document
        score = embedding_service._calculate_relevance_score(0.8, mock_chunk, None, query_terms)
        assert score >= 0.8
    
    def test_generate_citation_text(self, embedding_service):
        """Test citation text generation."""
        mock_chunk = Mock()
        mock_chunk.id = 1
        mock_chunk.position = 0
        
        mock_document = Mock()
        mock_document.id = 1
        mock_document.title = "Test Document"
        mock_document.url = "http://example.com"
        mock_document.filename = "test.pdf"
        
        mock_source = Mock()
        mock_source.name = "Test Source"
        mock_source.source_type = "url"
        mock_document.source = mock_source
        
        citation = embedding_service._generate_citation_text(mock_chunk, mock_document)
        
        assert "Test Document" in citation
        assert "http://example.com" in citation
    
    def test_extract_context_snippet(self, embedding_service):
        """Test context snippet extraction."""
        mock_chunk = Mock()
        mock_chunk.content = "This is a long document about machine learning and artificial intelligence. " * 10
        
        snippet = embedding_service._extract_context_snippet(mock_chunk, "machine learning", 100)
        
        assert len(snippet) <= 120  # Including potential "..."
        assert "machine learning" in snippet.lower()
    
    def test_calculate_citation_confidence(self, embedding_service):
        """Test citation confidence calculation."""
        mock_chunk = Mock()
        mock_chunk.token_count = 100
        
        mock_document = Mock()
        mock_document.processing_status = 'completed'
        mock_document.content_hash = 'abc123'
        mock_document.source = Mock()
        mock_document.source.status = 'completed'
        
        confidence = embedding_service._calculate_citation_confidence(mock_chunk, mock_document)
        
        assert 0.5 <= confidence <= 1.0


class TestEmbeddingIntegration:
    """Integration tests for embedding functionality."""
    
    def test_end_to_end_embedding_workflow(self, app, db_session):
        """Test complete embedding workflow from document to search."""
        with app.app_context():
            # This would be a more complex integration test
            # that tests the full workflow with real database
            pass
    
    def test_embedding_search_with_citations(self, app, db_session):
        """Test embedding search returns proper citations."""
        with app.app_context():
            # Test that search results include proper citation information
            pass
    
    def test_embedding_reindexing_workflow(self, app, db_session):
        """Test embedding re-indexing workflow."""
        with app.app_context():
            # Test that re-indexing properly updates embeddings
            pass