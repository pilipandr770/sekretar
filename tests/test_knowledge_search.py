"""Tests for knowledge search functionality."""
import pytest
from unittest.mock import Mock, patch, MagicMock
from app.services.knowledge_service import KnowledgeService
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app.utils.exceptions import ValidationError, ProcessingError


class TestKnowledgeSearch:
    """Test cases for knowledge search functionality."""
    
    def test_search_knowledge_vector_search_success(self):
        """Test successful vector-based knowledge search."""
        with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
            mock_service_instance = Mock()
            mock_embedding_service.return_value = mock_service_instance
            
            # Mock vector search results
            mock_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Test content',
                    'similarity_score': 0.9,
                    'citations': {
                        'source': 'Test Source',
                        'title': 'Test Document',
                        'url': 'http://example.com'
                    },
                    'metadata': {
                        'document_title': 'Test Document',
                        'source_name': 'Test Source'
                    }
                }
            ]
            mock_service_instance.search_similar_chunks.return_value = mock_results
            
            results = KnowledgeService.search_knowledge(
                tenant_id=1,
                query="test query",
                limit=10,
                min_similarity=0.7
            )
            
            assert len(results) == 1
            assert results[0]['similarity_score'] == 0.9
            assert 'citations' in results[0]
            
            mock_service_instance.search_similar_chunks.assert_called_once_with(
                tenant_id=1,
                query="test query",
                limit=10,
                min_similarity=0.7
            )
    
    def test_search_knowledge_fallback_to_text_search(self):
        """Test fallback to text search when vector search fails."""
        with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
            mock_service_instance = Mock()
            mock_embedding_service.return_value = mock_service_instance
            
            # Mock vector search failure
            mock_service_instance.search_similar_chunks.side_effect = Exception("Vector search failed")
            
            # Mock text search
            mock_document = Mock()
            mock_document.id = 1
            mock_document.title = "Test Document"
            mock_document.content = "This is test content with query terms"
            mock_document.url = "http://example.com"
            mock_document.source = Mock()
            mock_document.source.id = 1
            mock_document.source.name = "Test Source"
            mock_document.source.source_type = "url"
            mock_document.source.source_url = "http://example.com"
            
            with patch('app.models.knowledge.Document.query') as mock_query:
                mock_query.join.return_value.filter.return_value.limit.return_value.all.return_value = [mock_document]
                
                results = KnowledgeService.search_knowledge(
                    tenant_id=1,
                    query="test query",
                    limit=10,
                    min_similarity=0.7
                )
                
                assert len(results) == 1
                assert results[0]['document_id'] == 1
                assert results[0]['title'] == "Test Document"
                assert 'citations' in results[0]
                assert results[0]['metadata']['search_type'] == 'text_fallback'
    
    def test_search_knowledge_no_results(self):
        """Test knowledge search with no results."""
        with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
            mock_service_instance = Mock()
            mock_embedding_service.return_value = mock_service_instance
            
            # Mock empty vector search results
            mock_service_instance.search_similar_chunks.return_value = []
            
            # Mock empty text search results
            with patch('app.models.knowledge.Document.query') as mock_query:
                mock_query.join.return_value.filter.return_value.limit.return_value.all.return_value = []
                
                results = KnowledgeService.search_knowledge(
                    tenant_id=1,
                    query="nonexistent query",
                    limit=10,
                    min_similarity=0.7
                )
                
                assert results == []
    
    def test_search_knowledge_with_citations(self):
        """Test that search results include proper citations."""
        with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
            mock_service_instance = Mock()
            mock_embedding_service.return_value = mock_service_instance
            
            # Mock vector search results with citations
            mock_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Test content',
                    'similarity_score': 0.9,
                    'citations': {
                        'chunk_id': 1,
                        'position': 0,
                        'document_id': 1,
                        'document_title': 'Test Document',
                        'document_url': 'http://example.com',
                        'source_id': 1,
                        'source_name': 'Test Source',
                        'source_type': 'url',
                        'source_url': 'http://example.com'
                    },
                    'metadata': {
                        'chunk_position': 0,
                        'token_count': 100,
                        'document_title': 'Test Document',
                        'source_name': 'Test Source',
                        'source_type': 'url',
                        'url': 'http://example.com'
                    }
                }
            ]
            mock_service_instance.search_similar_chunks.return_value = mock_results
            
            results = KnowledgeService.search_knowledge(
                tenant_id=1,
                query="test query"
            )
            
            assert len(results) == 1
            result = results[0]
            
            # Check citations
            citations = result['citations']
            assert citations['chunk_id'] == 1
            assert citations['document_id'] == 1
            assert citations['document_title'] == 'Test Document'
            assert citations['source_name'] == 'Test Source'
            assert citations['source_url'] == 'http://example.com'
            
            # Check metadata
            metadata = result['metadata']
            assert metadata['chunk_position'] == 0
            assert metadata['token_count'] == 100
            assert metadata['document_title'] == 'Test Document'
    
    def test_search_knowledge_error_handling(self):
        """Test error handling in knowledge search."""
        with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
            mock_service_instance = Mock()
            mock_embedding_service.return_value = mock_service_instance
            
            # Mock both vector and text search failures
            mock_service_instance.search_similar_chunks.side_effect = Exception("Vector search failed")
            
            with patch('app.models.knowledge.Document.query') as mock_query:
                mock_query.join.side_effect = Exception("Database error")
                
                with pytest.raises(ProcessingError, match="Failed to search knowledge"):
                    KnowledgeService.search_knowledge(
                        tenant_id=1,
                        query="test query"
                    )
    
    def test_generate_embeddings_for_source(self):
        """Test embedding generation for knowledge source."""
        mock_source = Mock()
        mock_source.id = 1
        mock_source.tenant_id = 1
        
        mock_documents = [Mock(id=1), Mock(id=2)]
        
        with patch('app.models.knowledge.KnowledgeSource.get_by_id', return_value=mock_source):
            with patch('app.models.knowledge.Document.get_by_source', return_value=mock_documents):
                with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
                    mock_service_instance = Mock()
                    mock_embedding_service.return_value = mock_service_instance
                    
                    # Mock embedding creation
                    mock_service_instance.create_document_embeddings.side_effect = [
                        [Mock(), Mock()],  # 2 embeddings for doc 1
                        [Mock()]           # 1 embedding for doc 2
                    ]
                    
                    result = KnowledgeService.generate_embeddings(tenant_id=1, source_id=1)
                    
                    assert result['source_id'] == 1
                    assert result['documents_processed'] == 2
                    assert result['embeddings_created'] == 3
                    assert result['status'] == 'completed'
    
    def test_generate_embeddings_for_document(self):
        """Test embedding generation for specific document."""
        mock_document = Mock()
        mock_document.id = 1
        mock_document.tenant_id = 1
        
        with patch('app.models.knowledge.Document.get_by_id', return_value=mock_document):
            with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
                mock_service_instance = Mock()
                mock_embedding_service.return_value = mock_service_instance
                
                # Mock embedding creation
                mock_embeddings = [Mock(), Mock(), Mock()]
                mock_service_instance.create_document_embeddings.return_value = mock_embeddings
                
                result = KnowledgeService.generate_embeddings(tenant_id=1, document_id=1)
                
                assert result['document_id'] == 1
                assert result['embeddings_created'] == 3
                assert result['status'] == 'completed'
    
    def test_generate_embeddings_invalid_params(self):
        """Test embedding generation with invalid parameters."""
        with pytest.raises(ValidationError, match="Either source_id or document_id must be provided"):
            KnowledgeService.generate_embeddings(tenant_id=1)
    
    def test_generate_embeddings_source_not_found(self):
        """Test embedding generation with non-existent source."""
        with patch('app.models.knowledge.KnowledgeSource.get_by_id', return_value=None):
            with pytest.raises(ValidationError, match="Knowledge source not found"):
                KnowledgeService.generate_embeddings(tenant_id=1, source_id=999)
    
    def test_generate_embeddings_document_not_found(self):
        """Test embedding generation with non-existent document."""
        with patch('app.models.knowledge.Document.get_by_id', return_value=None):
            with pytest.raises(ValidationError, match="Document not found"):
                KnowledgeService.generate_embeddings(tenant_id=1, document_id=999)
    
    def test_reindex_embeddings_success(self):
        """Test successful embedding re-indexing."""
        with patch('app.services.knowledge_service.EmbeddingService') as mock_embedding_service:
            mock_service_instance = Mock()
            mock_embedding_service.return_value = mock_service_instance
            
            mock_result = {
                'source_id': 1,
                'documents_processed': 5,
                'embeddings_created': 20,
                'embeddings_updated': 15
            }
            mock_service_instance.reindex_knowledge_source.return_value = mock_result
            
            result = KnowledgeService.reindex_embeddings(tenant_id=1, source_id=1)
            
            assert result == mock_result
            mock_service_instance.reindex_knowledge_source.assert_called_once_with(1, 1)
    
    def test_get_embedding_stats_success(self):
        """Test successful embedding statistics retrieval."""
        mock_stats = {
            'total_embeddings': 100,
            'embeddings_by_model': {
                'text-embedding-ada-002': 80,
                'text-embedding-3-small': 20
            },
            'total_chunks': 120,
            'embedded_chunks': 100,
            'embedding_coverage': 83.33
        }
        
        with patch('app.services.knowledge_service.EmbeddingService.get_embedding_stats', return_value=mock_stats):
            result = KnowledgeService.get_embedding_stats(tenant_id=1)
            assert result == mock_stats
    
    def test_get_embedding_stats_error(self):
        """Test embedding statistics retrieval with error."""
        with patch('app.services.knowledge_service.EmbeddingService.get_embedding_stats', side_effect=Exception("Stats error")):
            with pytest.raises(ProcessingError, match="Failed to get embedding stats"):
                KnowledgeService.get_embedding_stats(tenant_id=1)


class TestKnowledgeSearchAPI:
    """Test cases for knowledge search API endpoints."""
    
    def test_search_endpoint_success(self, client, auth_headers):
        """Test successful search API endpoint."""
        mock_results = [
            {
                'chunk_id': 1,
                'document_id': 1,
                'content': 'Test content',
                'similarity_score': 0.9,
                'citations': {
                    'source': 'Test Source',
                    'title': 'Test Document'
                }
            }
        ]
        
        with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_results):
            response = client.post(
                '/api/v1/knowledge/search',
                json={
                    'query': 'test query',
                    'limit': 10,
                    'min_similarity': 0.7
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert len(data['data']['results']) == 1
            assert data['data']['query'] == 'test query'
    
    def test_search_endpoint_validation_error(self, client, auth_headers):
        """Test search endpoint with validation error."""
        response = client.post(
            '/api/v1/knowledge/search',
            json={
                'query': '',  # Empty query
                'limit': 10
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'empty' in data['error']['message'].lower()
    
    def test_search_endpoint_invalid_limit(self, client, auth_headers):
        """Test search endpoint with invalid limit."""
        response = client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test query',
                'limit': 100  # Too high
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'limit' in data['error']['message'].lower()
    
    def test_search_endpoint_invalid_similarity(self, client, auth_headers):
        """Test search endpoint with invalid similarity threshold."""
        response = client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test query',
                'min_similarity': 1.5  # Too high
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert data['success'] is False
        assert 'similarity' in data['error']['message'].lower()
    
    def test_generate_source_embeddings_endpoint(self, client, auth_headers):
        """Test generate source embeddings endpoint."""
        mock_result = {
            'source_id': 1,
            'documents_processed': 5,
            'embeddings_created': 20,
            'status': 'completed'
        }
        
        with patch('app.services.knowledge_service.KnowledgeService.generate_embeddings', return_value=mock_result):
            response = client.post(
                '/api/v1/knowledge/sources/1/embeddings',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['source_id'] == 1
            assert data['data']['embeddings_created'] == 20
    
    def test_generate_document_embeddings_endpoint(self, client, auth_headers):
        """Test generate document embeddings endpoint."""
        mock_result = {
            'document_id': 1,
            'embeddings_created': 5,
            'status': 'completed'
        }
        
        with patch('app.services.knowledge_service.KnowledgeService.generate_embeddings', return_value=mock_result):
            response = client.post(
                '/api/v1/knowledge/documents/1/embeddings',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['document_id'] == 1
            assert data['data']['embeddings_created'] == 5
    
    def test_reindex_source_embeddings_endpoint(self, client, auth_headers):
        """Test reindex source embeddings endpoint."""
        mock_result = {
            'source_id': 1,
            'documents_processed': 5,
            'embeddings_created': 15,
            'embeddings_updated': 10
        }
        
        with patch('app.services.knowledge_service.KnowledgeService.reindex_embeddings', return_value=mock_result):
            response = client.post(
                '/api/v1/knowledge/sources/1/reindex',
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert data['data']['source_id'] == 1
            assert data['data']['embeddings_created'] == 15
    
    def test_knowledge_stats_with_embeddings(self, client, auth_headers):
        """Test knowledge stats endpoint includes embedding statistics."""
        mock_embedding_stats = {
            'total_embeddings': 100,
            'embeddings_by_model': {'text-embedding-ada-002': 100},
            'total_chunks': 120,
            'embedded_chunks': 100,
            'embedding_coverage': 83.33
        }
        
        with patch('app.services.knowledge_service.KnowledgeService.get_embedding_stats', return_value=mock_embedding_stats):
            with patch('app.models.knowledge.KnowledgeSource.query') as mock_source_query:
                with patch('app.models.knowledge.Document.query') as mock_doc_query:
                    with patch('app.models.knowledge.Chunk.query') as mock_chunk_query:
                        # Mock database queries
                        mock_source_query.filter_by.return_value.with_entities.return_value.group_by.return_value.all.return_value = []
                        mock_doc_query.filter_by.return_value.with_entities.return_value.first.return_value = Mock(total_documents=10, total_tokens=1000)
                        mock_chunk_query.filter_by.return_value.with_entities.return_value.first.return_value = Mock(total_chunks=120)
                        
                        response = client.get(
                            '/api/v1/knowledge/stats',
                            headers=auth_headers
                        )
                        
                        assert response.status_code == 200
                        data = response.get_json()
                        assert data['success'] is True
                        assert 'embeddings' in data['data']
                        assert data['data']['embeddings']['total_embeddings'] == 100
                        assert data['data']['embeddings']['embedding_coverage'] == 83.33