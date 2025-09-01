"""Comprehensive tests for knowledge management functionality."""
import pytest
from io import BytesIO
from unittest.mock import patch, Mock
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app.services.knowledge_service import KnowledgeService
from app.utils.exceptions import ValidationError, ProcessingError


class TestKnowledgeDocumentProcessing:
    """Test knowledge document processing functionality."""
    
    def test_create_document_source(self, app, tenant, db_session):
        """Test creating a document-based knowledge source."""
        with app.app_context():
            # Refresh tenant in current session
            db_session.add(tenant)
            db_session.refresh(tenant)
            
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Test Documents',
                description='Test document source',
                tags=['test', 'documents']
            )
            source.save()
            
            assert source.id is not None
            assert source.name == 'Test Documents'
            assert source.source_type == 'document'
            assert source.status == 'pending'
            assert 'test' in source.tags
    
    def test_upload_document_processing(self, app, client, tenant, auth_headers):
        """Test document upload and processing."""
        with app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Test Documents'
            )
            source.save()
            
            # Create test file
            test_content = "This is a comprehensive test document for knowledge management."
            test_file = BytesIO(test_content.encode('utf-8'))
            test_file.name = 'test.txt'
            
            # Mock document processing
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.return_value = {
                    'content': test_content,
                    'token_count': 12,
                    'content_hash': 'test_hash_123',
                    'file_size': len(test_content),
                    'mime_type': 'text/plain',
                    'file_extension': 'txt',
                    'metadata': {'format': 'plain_text'}
                }
                
                mock_processor.chunk_text.return_value = [
                    {
                        'content': test_content,
                        'position': 0,
                        'token_count': 12,
                        'overlap_start': 0,
                        'overlap_end': 0
                    }
                ]
                
                response = client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file, 'test.txt', 'text/plain'),
                        'title': 'Test Document'
                    },
                    headers=auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response.status_code == 201
                data = response.json
                assert data['success'] is True
                assert data['data']['document']['title'] == 'Test Document'
                assert data['data']['document']['filename'] == 'test.txt'
    
    def test_generate_embeddings(self, app, client, tenant, auth_headers):
        """Test embedding generation for documents."""
        with app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Embedding Test'
            )
            source.save()
            
            # Mock embedding generation
            with patch('app.services.knowledge_service.KnowledgeService.generate_embeddings') as mock_generate:
                mock_generate.return_value = {
                    'source_id': source.id,
                    'documents_processed': 1,
                    'embeddings_created': 1,
                    'status': 'completed'
                }
                
                response = client.post(
                    f'/api/v1/knowledge/sources/{source.id}/embeddings',
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['source_id'] == source.id
                assert data['data']['embeddings_created'] == 1
    
    def test_reindex_embeddings(self, app, client, tenant, auth_headers):
        """Test re-indexing embeddings for a source."""
        with app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Reindex Test'
            )
            source.save()
            
            # Mock reindexing
            with patch('app.services.knowledge_service.KnowledgeService.reindex_embeddings') as mock_reindex:
                mock_reindex.return_value = {
                    'source_id': source.id,
                    'documents_processed': 2,
                    'embeddings_created': 3,
                    'embeddings_updated': 1,
                    'status': 'completed'
                }
                
                response = client.post(
                    f'/api/v1/knowledge/sources/{source.id}/reindex',
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['embeddings_created'] == 3
                assert data['data']['embeddings_updated'] == 1


class TestKnowledgeSearch:
    """Test knowledge search functionality."""
    
    def test_vector_search(self, app, client, tenant, auth_headers):
        """Test vector-based knowledge search."""
        with app.app_context():
            # Mock search results
            mock_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Python is a high-level programming language.',
                    'similarity_score': 0.92,
                    'title': 'Python Guide',
                    'relevance_score': 0.92,
                    'citations': {
                        'document_title': 'Python Guide',
                        'source_name': 'Technical Docs'
                    },
                    'metadata': {
                        'search_type': 'vector',
                        'token_count': 8
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_results):
                response = client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'Python programming language',
                        'limit': 10,
                        'min_similarity': 0.8
                    },
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                assert data['data']['results'][0]['similarity_score'] == 0.92
                assert 'citations' in data['data']['results'][0]
    
    def test_search_with_filtering(self, app, client, tenant, auth_headers):
        """Test search with source filtering."""
        with app.app_context():
            # Create test sources
            source1 = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='HR Docs'
            )
            source1.save()
            
            source2 = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Tech Docs'
            )
            source2.save()
            
            # Mock filtered search results
            mock_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Employee policies and procedures.',
                    'similarity_score': 0.88,
                    'title': 'HR Handbook',
                    'relevance_score': 0.88,
                    'citations': {
                        'source_id': source1.id,
                        'source_name': 'HR Docs'
                    },
                    'metadata': {'search_type': 'vector'}
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_results):
                response = client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'employee policies',
                        'limit': 10,
                        'source_ids': [source1.id]
                    },
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                assert data['data']['results'][0]['citations']['source_name'] == 'HR Docs'
    
    def test_search_validation(self, app, client, auth_headers):
        """Test search input validation."""
        # Test empty query
        response = client.post(
            '/api/v1/knowledge/search',
            json={'query': '   '},
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'empty' in data['error']['message'].lower()
        
        # Test invalid limit
        response = client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test',
                'limit': 100  # Too high
            },
            headers=auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'limit' in data['error']['message'].lower()


class TestRAGFunctionality:
    """Test Retrieval Augmented Generation functionality."""
    
    def test_rag_context_retrieval(self, app, client, auth_headers):
        """Test RAG context retrieval for AI responses."""
        # Mock RAG search results with context
        mock_rag_results = [
            {
                'chunk_id': 1,
                'document_id': 1,
                'content': 'Our return policy allows returns within 30 days with receipt.',
                'similarity_score': 0.94,
                'title': 'Return Policy',
                'relevance_score': 0.94,
                'citations': {
                    'document_title': 'Return Policy',
                    'source_name': 'Company Policies',
                    'section': 'Customer Service'
                },
                'metadata': {
                    'search_type': 'vector',
                    'context_type': 'policy',
                    'confidence': 0.94
                }
            }
        ]
        
        with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_rag_results):
            response = client.post(
                '/api/v1/knowledge/search',
                json={
                    'query': 'customer wants to return item',
                    'limit': 5,
                    'min_similarity': 0.8
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert len(data['data']['results']) == 1
            
            result = data['data']['results'][0]
            assert 'return policy' in result['content'].lower()
            assert result['citations']['section'] == 'Customer Service'
            assert result['metadata']['context_type'] == 'policy'
    
    def test_rag_multi_document_context(self, app, client, auth_headers):
        """Test RAG with context from multiple documents."""
        mock_results = [
            {
                'chunk_id': 1,
                'document_id': 1,
                'content': 'Python is an interpreted programming language.',
                'similarity_score': 0.93,
                'title': 'Python Intro',
                'relevance_score': 0.93,
                'citations': {'document_title': 'Python Intro'},
                'metadata': {'context_type': 'definition'}
            },
            {
                'chunk_id': 2,
                'document_id': 2,
                'content': 'Python supports object-oriented programming.',
                'similarity_score': 0.91,
                'title': 'Python Features',
                'relevance_score': 0.91,
                'citations': {'document_title': 'Python Features'},
                'metadata': {'context_type': 'features'}
            }
        ]
        
        with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_results):
            response = client.post(
                '/api/v1/knowledge/search',
                json={
                    'query': 'explain Python programming',
                    'limit': 10,
                    'min_similarity': 0.8
                },
                headers=auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert len(data['data']['results']) == 2
            
            # Verify comprehensive context from multiple documents
            context_types = [r['metadata']['context_type'] for r in data['data']['results']]
            assert 'definition' in context_types
            assert 'features' in context_types


class TestKnowledgeModels:
    """Test knowledge management models."""
    
    def test_knowledge_source_creation(self, app, tenant):
        """Test creating knowledge sources."""
        with app.app_context():
            # Test document source
            doc_source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name="Test Documents"
            )
            
            assert doc_source.source_type == "document"
            assert doc_source.source_url is None
            assert doc_source.status == "pending"
            
            # Test URL source
            url_source = KnowledgeSource.create_url_source(
                tenant_id=tenant.id,
                name="Test Website",
                url="https://example.com"
            )
            
            assert url_source.source_type == "url"
            assert url_source.source_url == "https://example.com"
    
    def test_document_creation(self, app, tenant):
        """Test creating documents."""
        with app.app_context():
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name="Test Source"
            )
            source.save()
            
            document = Document.create(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document",
                content="Test content for document processing.",
                token_count=6
            )
            document.save()
            
            assert document.id is not None
            assert document.title == "Test Document"
            assert document.processing_status == "pending"
            assert document.token_count == 6
    
    def test_chunk_creation(self, app, tenant):
        """Test creating text chunks."""
        with app.app_context():
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name="Test Source"
            )
            source.save()
            
            document = Document.create(
                tenant_id=tenant.id,
                source_id=source.id,
                title="Test Document",
                content="Long document content that needs chunking."
            )
            document.save()
            
            chunk = Chunk.create(
                tenant_id=tenant.id,
                document_id=document.id,
                content="Long document content that needs chunking.",
                position=0,
                token_count=8
            )
            chunk.save()
            
            assert chunk.id is not None
            assert chunk.position == 0
            assert chunk.token_count == 8
            assert chunk.document_id == document.id
    
    def test_embedding_operations(self, app, tenant):
        """Test embedding creation and operations."""
        with app.app_context():
            import numpy as np
            
            # Create chunk for embedding
            chunk = Chunk.create(
                tenant_id=tenant.id,
                content="Test content for embedding",
                position=0
            )
            chunk.save()
            
            # Create embedding
            test_vector = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
            embedding = Embedding.create_from_vector(
                tenant_id=tenant.id,
                chunk_id=chunk.id,
                vector=test_vector,
                model_name="text-embedding-ada-002"
            )
            
            assert embedding.id is not None
            assert embedding.model_name == "text-embedding-ada-002"
            assert embedding.dimension == 5
            
            # Test vector retrieval
            retrieved_vector = embedding.get_vector()
            np.testing.assert_array_equal(retrieved_vector, test_vector)
            
            # Test similarity calculation
            similar_vector = np.array([0.2, 0.3, 0.4, 0.5, 0.6])
            similarity = embedding.calculate_similarity(similar_vector)
            assert similarity > 0.8  # Should be high similarity


class TestKnowledgeStatistics:
    """Test knowledge base statistics."""
    
    def test_knowledge_stats_endpoint(self, app, client, tenant, auth_headers):
        """Test knowledge statistics endpoint."""
        with app.app_context():
            # Create test data
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Stats Test Source'
            )
            source.mark_as_completed()
            source.save()
            
            doc = Document.create(
                tenant_id=tenant.id,
                source_id=source.id,
                title='Stats Test Doc',
                content='Test content',
                token_count=2
            )
            doc.save()
            
            # Mock embedding stats
            mock_stats = {
                'total_embeddings': 1,
                'embeddings_by_model': {'text-embedding-ada-002': 1},
                'total_chunks': 1,
                'embedded_chunks': 1,
                'embedding_coverage': 100.0
            }
            
            with patch('app.services.knowledge_service.KnowledgeService.get_embedding_stats', return_value=mock_stats):
                response = client.get(
                    '/api/v1/knowledge/stats',
                    headers=auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                
                stats = data['data']
                assert stats['sources']['total'] == 1
                assert stats['sources']['active'] == 1
                assert stats['documents']['total'] == 1
                assert stats['documents']['total_tokens'] == 2
                assert stats['embeddings']['total_embeddings'] == 1
                assert stats['embeddings']['embedding_coverage'] == 100.0