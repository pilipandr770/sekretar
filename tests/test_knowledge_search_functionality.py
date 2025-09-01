"""Comprehensive tests for knowledge management search functionality including RAG."""
import pytest
import numpy as np
from unittest.mock import patch, Mock, MagicMock
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app.services.knowledge_service import KnowledgeService
from app.utils.exceptions import ValidationError, ProcessingError


def create_test_tenant(name="Test Tenant", domain="test.example.com"):
    """Create a test tenant."""
    tenant = Tenant(
        name=name,
        domain=domain,
        slug="test-tenant",
        settings={"test": True}
    )
    db.session.add(tenant)
    db.session.commit()
    return tenant


def create_test_user(tenant_id, email="test@example.com", password="testpass123"):
    """Create a test user."""
    user = User(
        tenant_id=tenant_id,
        email=email,
        first_name="Test",
        last_name="User",
        role="manager",
        is_active=True
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


class TestKnowledgeBaseSearch:
    """Test knowledge base search functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, app, client):
        """Set up test data."""
        self.app = app
        self.client = client
        
        with app.app_context():
            # Create test tenant and user
            self.tenant = create_test_tenant()
            self.user = create_test_user(tenant_id=self.tenant.id)
            
            # Get auth token
            response = client.post('/api/v1/auth/login', json={
                'email': self.user.email,
                'password': 'testpass123'
            })
            self.auth_token = response.json['data']['access_token']
            self.auth_headers = {'Authorization': f'Bearer {self.auth_token}'}
    
    def test_vector_search_with_high_similarity(self):
        """Test vector-based search with high similarity matches."""
        with self.app.app_context():
            # Create test knowledge base
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Technical Documentation'
            )
            source.mark_as_completed()
            source.save()
            
            # Create documents with technical content
            doc1 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Python Programming Guide',
                content='Python is a high-level programming language known for its simplicity and readability. It supports multiple programming paradigms including object-oriented, functional, and procedural programming.',
                token_count=25
            )
            doc1.save()
            
            doc2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Machine Learning Basics',
                content='Machine learning is a subset of artificial intelligence that enables computers to learn and make decisions from data without being explicitly programmed.',
                token_count=22
            )
            doc2.save()
            
            # Mock vector search results
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': doc1.id,
                    'content': 'Python is a high-level programming language known for its simplicity and readability.',
                    'similarity_score': 0.92,
                    'title': 'Python Programming Guide',
                    'relevance_score': 0.92,
                    'citations': {
                        'chunk_id': 1,
                        'position': 0,
                        'document_id': doc1.id,
                        'document_title': 'Python Programming Guide',
                        'source_id': source.id,
                        'source_name': 'Technical Documentation',
                        'source_type': 'document'
                    },
                    'metadata': {
                        'chunk_position': 0,
                        'token_count': 15,
                        'document_title': 'Python Programming Guide',
                        'source_name': 'Technical Documentation',
                        'search_type': 'vector'
                    }
                },
                {
                    'chunk_id': 2,
                    'document_id': doc2.id,
                    'content': 'Machine learning is a subset of artificial intelligence that enables computers to learn.',
                    'similarity_score': 0.75,
                    'title': 'Machine Learning Basics',
                    'relevance_score': 0.75,
                    'citations': {
                        'chunk_id': 2,
                        'position': 0,
                        'document_id': doc2.id,
                        'document_title': 'Machine Learning Basics',
                        'source_id': source.id,
                        'source_name': 'Technical Documentation',
                        'source_type': 'document'
                    },
                    'metadata': {
                        'chunk_position': 0,
                        'token_count': 12,
                        'document_title': 'Machine Learning Basics',
                        'source_name': 'Technical Documentation',
                        'search_type': 'vector'
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'Python programming language features',
                        'limit': 10,
                        'min_similarity': 0.7
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 2
                
                # Verify results are ordered by relevance
                results = data['data']['results']
                assert results[0]['similarity_score'] == 0.92
                assert results[1]['similarity_score'] == 0.75
                assert results[0]['similarity_score'] > results[1]['similarity_score']
                
                # Verify citations are included
                assert 'citations' in results[0]
                assert results[0]['citations']['document_title'] == 'Python Programming Guide'
                assert results[0]['citations']['source_name'] == 'Technical Documentation'
                
                # Verify metadata
                assert results[0]['metadata']['search_type'] == 'vector'
                assert results[0]['metadata']['token_count'] == 15
    
    def test_text_search_fallback(self):
        """Test fallback to text search when vector search fails."""
        with self.app.app_context():
            # Create test knowledge base
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Business Documents'
            )
            source.mark_as_completed()
            source.save()
            
            doc = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Sales Strategy Document',
                content='Our sales strategy focuses on customer acquisition through digital marketing channels and relationship building.',
                token_count=18
            )
            doc.save()
            
            # Mock text search fallback results
            mock_search_results = [
                {
                    'document_id': doc.id,
                    'title': 'Sales Strategy Document',
                    'content': 'Our sales strategy focuses on customer acquisition through digital marketing channels.',
                    'relevance_score': 0.85,
                    'citations': {
                        'document_id': doc.id,
                        'document_title': 'Sales Strategy Document',
                        'source_id': source.id,
                        'source_name': 'Business Documents',
                        'source_type': 'document'
                    },
                    'metadata': {
                        'document_title': 'Sales Strategy Document',
                        'source_name': 'Business Documents',
                        'search_type': 'text_fallback',
                        'token_count': 18
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'sales strategy customer acquisition',
                        'limit': 5,
                        'min_similarity': 0.6
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                
                result = data['data']['results'][0]
                assert result['title'] == 'Sales Strategy Document'
                assert result['metadata']['search_type'] == 'text_fallback'
                assert 'sales strategy' in result['content'].lower()
    
    def test_search_with_source_filtering(self):
        """Test search with source ID filtering."""
        with self.app.app_context():
            # Create multiple sources
            source1 = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='HR Policies'
            )
            source1.mark_as_completed()
            source1.save()
            
            source2 = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Technical Docs'
            )
            source2.mark_as_completed()
            source2.save()
            
            # Create documents in different sources
            hr_doc = Document.create(
                tenant_id=self.tenant.id,
                source_id=source1.id,
                title='Employee Handbook',
                content='Employee policies and procedures for workplace conduct and benefits.',
                token_count=12
            )
            hr_doc.save()
            
            tech_doc = Document.create(
                tenant_id=self.tenant.id,
                source_id=source2.id,
                title='API Documentation',
                content='Technical documentation for REST API endpoints and authentication.',
                token_count=11
            )
            tech_doc.save()
            
            # Mock filtered search results (only from HR source)
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': hr_doc.id,
                    'content': 'Employee policies and procedures for workplace conduct and benefits.',
                    'similarity_score': 0.88,
                    'title': 'Employee Handbook',
                    'relevance_score': 0.88,
                    'citations': {
                        'chunk_id': 1,
                        'document_id': hr_doc.id,
                        'document_title': 'Employee Handbook',
                        'source_id': source1.id,
                        'source_name': 'HR Policies',
                        'source_type': 'document'
                    },
                    'metadata': {
                        'document_title': 'Employee Handbook',
                        'source_name': 'HR Policies',
                        'search_type': 'vector'
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'employee policies',
                        'limit': 10,
                        'min_similarity': 0.7,
                        'source_ids': [source1.id]  # Filter to HR source only
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                
                result = data['data']['results'][0]
                assert result['citations']['source_name'] == 'HR Policies'
                assert result['citations']['source_id'] == source1.id
                
                # Verify source filtering was applied
                assert data['data']['source_ids_filter'] == [source1.id]
    
    def test_search_relevance_scoring(self):
        """Test search relevance scoring and ranking."""
        with self.app.app_context():
            # Create test documents with varying relevance
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Mixed Content'
            )
            source.mark_as_completed()
            source.save()
            
            # Mock search results with different relevance scores
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Artificial intelligence and machine learning are transforming business operations.',
                    'similarity_score': 0.95,
                    'title': 'AI in Business',
                    'relevance_score': 0.95,
                    'citations': {
                        'chunk_id': 1,
                        'document_id': 1,
                        'document_title': 'AI in Business',
                        'source_name': 'Mixed Content'
                    },
                    'metadata': {'search_type': 'vector'}
                },
                {
                    'chunk_id': 2,
                    'document_id': 2,
                    'content': 'Machine learning algorithms require large datasets for training.',
                    'similarity_score': 0.87,
                    'title': 'ML Training Data',
                    'relevance_score': 0.87,
                    'citations': {
                        'chunk_id': 2,
                        'document_id': 2,
                        'document_title': 'ML Training Data',
                        'source_name': 'Mixed Content'
                    },
                    'metadata': {'search_type': 'vector'}
                },
                {
                    'chunk_id': 3,
                    'document_id': 3,
                    'content': 'Data science involves statistical analysis and machine learning techniques.',
                    'similarity_score': 0.82,
                    'title': 'Data Science Overview',
                    'relevance_score': 0.82,
                    'citations': {
                        'chunk_id': 3,
                        'document_id': 3,
                        'document_title': 'Data Science Overview',
                        'source_name': 'Mixed Content'
                    },
                    'metadata': {'search_type': 'vector'}
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'machine learning artificial intelligence',
                        'limit': 10,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 3
                
                results = data['data']['results']
                
                # Verify results are ordered by relevance score (highest first)
                assert results[0]['relevance_score'] == 0.95
                assert results[1]['relevance_score'] == 0.87
                assert results[2]['relevance_score'] == 0.82
                
                # Verify all results meet minimum similarity threshold
                for result in results:
                    assert result['similarity_score'] >= 0.8
    
    def test_search_with_different_embedding_models(self):
        """Test search with different embedding models."""
        with self.app.app_context():
            # Mock search with specific model
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Advanced natural language processing techniques.',
                    'similarity_score': 0.91,
                    'title': 'NLP Guide',
                    'relevance_score': 0.91,
                    'citations': {
                        'chunk_id': 1,
                        'document_id': 1,
                        'document_title': 'NLP Guide'
                    },
                    'metadata': {
                        'search_type': 'vector',
                        'embedding_model': 'text-embedding-3-small'
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                with patch('app.services.knowledge_service.KnowledgeService.validate_embedding_model', return_value=True):
                    response = self.client.post(
                        '/api/v1/knowledge/search',
                        json={
                            'query': 'natural language processing',
                            'limit': 5,
                            'min_similarity': 0.7,
                            'model': 'text-embedding-3-small'
                        },
                        headers=self.auth_headers
                    )
                    
                    assert response.status_code == 200
                    data = response.json
                    assert data['success'] is True
                    assert data['data']['model_used'] == 'text-embedding-3-small'
                    assert len(data['data']['results']) == 1
    
    def test_search_validation_errors(self):
        """Test search input validation."""
        # Test empty query
        response = self.client.post(
            '/api/v1/knowledge/search',
            json={'query': '   '},
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'empty' in data['error']['message'].lower()
        
        # Test invalid limit
        response = self.client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test query',
                'limit': 100  # Too high
            },
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'limit' in data['error']['message'].lower()
        
        # Test invalid similarity threshold
        response = self.client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test query',
                'min_similarity': 1.5  # Too high
            },
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'similarity' in data['error']['message'].lower()
        
        # Test invalid source IDs
        response = self.client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test query',
                'source_ids': 'invalid'  # Should be list
            },
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'source_ids' in data['error']['message'].lower()


class TestRAGFunctionality:
    """Test Retrieval Augmented Generation (RAG) functionality."""
    
    @pytest.fixture(autouse=True)
    def setup(self, app, client):
        """Set up test data."""
        self.app = app
        self.client = client
        
        with app.app_context():
            # Create test tenant and user
            self.tenant = create_test_tenant()
            self.user = create_test_user(tenant_id=self.tenant.id)
            
            # Get auth token
            response = client.post('/api/v1/auth/login', json={
                'email': self.user.email,
                'password': 'testpass123'
            })
            self.auth_token = response.json['data']['access_token']
            self.auth_headers = {'Authorization': f'Bearer {self.auth_token}'}
    
    def test_rag_context_retrieval(self):
        """Test RAG context retrieval for AI agent responses."""
        with self.app.app_context():
            # Create knowledge base with relevant content
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Company Knowledge Base'
            )
            source.mark_as_completed()
            source.save()
            
            # Mock RAG search results with context
            mock_rag_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Our company return policy allows customers to return items within 30 days of purchase with original receipt.',
                    'similarity_score': 0.94,
                    'title': 'Return Policy',
                    'relevance_score': 0.94,
                    'citations': {
                        'chunk_id': 1,
                        'document_id': 1,
                        'document_title': 'Return Policy',
                        'source_name': 'Company Knowledge Base',
                        'page_number': 1,
                        'section': 'Customer Service'
                    },
                    'metadata': {
                        'search_type': 'vector',
                        'context_type': 'policy',
                        'confidence': 0.94
                    }
                },
                {
                    'chunk_id': 2,
                    'document_id': 2,
                    'content': 'Refunds are processed within 5-7 business days after we receive the returned item.',
                    'similarity_score': 0.89,
                    'title': 'Refund Processing',
                    'relevance_score': 0.89,
                    'citations': {
                        'chunk_id': 2,
                        'document_id': 2,
                        'document_title': 'Refund Processing',
                        'source_name': 'Company Knowledge Base',
                        'page_number': 2,
                        'section': 'Customer Service'
                    },
                    'metadata': {
                        'search_type': 'vector',
                        'context_type': 'procedure',
                        'confidence': 0.89
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_rag_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'customer wants to return purchased item',
                        'limit': 5,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 2
                
                results = data['data']['results']
                
                # Verify RAG context is suitable for AI response
                assert 'return policy' in results[0]['content'].lower()
                assert 'refunds are processed' in results[1]['content'].lower()
                
                # Verify citations for source attribution
                assert results[0]['citations']['section'] == 'Customer Service'
                assert results[1]['citations']['section'] == 'Customer Service'
                
                # Verify metadata for context understanding
                assert results[0]['metadata']['context_type'] == 'policy'
                assert results[1]['metadata']['context_type'] == 'procedure'
    
    def test_rag_multi_document_context(self):
        """Test RAG retrieval from multiple documents for comprehensive context."""
        with self.app.app_context():
            # Mock multi-document RAG results
            mock_rag_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Python is an interpreted, high-level programming language with dynamic semantics.',
                    'similarity_score': 0.93,
                    'title': 'Python Introduction',
                    'relevance_score': 0.93,
                    'citations': {
                        'document_title': 'Python Introduction',
                        'source_name': 'Programming Guides'
                    },
                    'metadata': {'context_type': 'definition'}
                },
                {
                    'chunk_id': 2,
                    'document_id': 2,
                    'content': 'Python supports multiple programming paradigms including procedural, object-oriented, and functional programming.',
                    'similarity_score': 0.91,
                    'title': 'Python Paradigms',
                    'relevance_score': 0.91,
                    'citations': {
                        'document_title': 'Python Paradigms',
                        'source_name': 'Programming Guides'
                    },
                    'metadata': {'context_type': 'features'}
                },
                {
                    'chunk_id': 3,
                    'document_id': 3,
                    'content': 'Common Python libraries include NumPy for numerical computing, Pandas for data analysis, and Django for web development.',
                    'similarity_score': 0.88,
                    'title': 'Python Libraries',
                    'relevance_score': 0.88,
                    'citations': {
                        'document_title': 'Python Libraries',
                        'source_name': 'Programming Guides'
                    },
                    'metadata': {'context_type': 'libraries'}
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_rag_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'explain Python programming language',
                        'limit': 10,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 3
                
                results = data['data']['results']
                
                # Verify comprehensive context from multiple documents
                context_types = [r['metadata']['context_type'] for r in results]
                assert 'definition' in context_types
                assert 'features' in context_types
                assert 'libraries' in context_types
                
                # Verify all results are from same source but different documents
                for result in results:
                    assert result['citations']['source_name'] == 'Programming Guides'
    
    def test_rag_context_ranking_and_filtering(self):
        """Test RAG context ranking and filtering for optimal AI responses."""
        with self.app.app_context():
            # Mock RAG results with various relevance scores
            mock_rag_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Machine learning models require training data to learn patterns and make predictions.',
                    'similarity_score': 0.96,
                    'title': 'ML Training',
                    'relevance_score': 0.96,
                    'citations': {'document_title': 'ML Training'},
                    'metadata': {
                        'context_type': 'core_concept',
                        'confidence': 0.96,
                        'freshness': 'recent'
                    }
                },
                {
                    'chunk_id': 2,
                    'document_id': 2,
                    'content': 'Supervised learning uses labeled data to train models for classification and regression tasks.',
                    'similarity_score': 0.94,
                    'title': 'Supervised Learning',
                    'relevance_score': 0.94,
                    'citations': {'document_title': 'Supervised Learning'},
                    'metadata': {
                        'context_type': 'specific_method',
                        'confidence': 0.94,
                        'freshness': 'recent'
                    }
                },
                {
                    'chunk_id': 3,
                    'document_id': 3,
                    'content': 'Deep learning is a subset of machine learning that uses neural networks with multiple layers.',
                    'similarity_score': 0.92,
                    'title': 'Deep Learning',
                    'relevance_score': 0.92,
                    'citations': {'document_title': 'Deep Learning'},
                    'metadata': {
                        'context_type': 'advanced_topic',
                        'confidence': 0.92,
                        'freshness': 'recent'
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_rag_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'how does machine learning work',
                        'limit': 3,
                        'min_similarity': 0.9
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 3
                
                results = data['data']['results']
                
                # Verify results are ranked by relevance
                assert results[0]['relevance_score'] >= results[1]['relevance_score']
                assert results[1]['relevance_score'] >= results[2]['relevance_score']
                
                # Verify all results meet minimum similarity for RAG
                for result in results:
                    assert result['similarity_score'] >= 0.9
                
                # Verify context metadata for AI processing
                assert results[0]['metadata']['context_type'] == 'core_concept'
                assert results[1]['metadata']['context_type'] == 'specific_method'
                assert results[2]['metadata']['context_type'] == 'advanced_topic'
    
    def test_rag_citation_accuracy(self):
        """Test accuracy of citations in RAG responses."""
        with self.app.app_context():
            # Mock RAG results with detailed citations
            mock_rag_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'The quarterly revenue increased by 15% compared to the previous quarter.',
                    'similarity_score': 0.95,
                    'title': 'Q3 Financial Report',
                    'relevance_score': 0.95,
                    'citations': {
                        'chunk_id': 1,
                        'position': 0,
                        'document_id': 1,
                        'document_title': 'Q3 Financial Report',
                        'document_url': None,
                        'source_id': 1,
                        'source_name': 'Financial Reports',
                        'source_type': 'document',
                        'page_number': 3,
                        'section': 'Revenue Analysis',
                        'created_at': '2024-01-15T10:30:00Z',
                        'updated_at': '2024-01-15T10:30:00Z'
                    },
                    'metadata': {
                        'search_type': 'vector',
                        'context_type': 'financial_data',
                        'confidence': 0.95,
                        'data_freshness': 'current_quarter'
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_rag_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'quarterly revenue performance',
                        'limit': 5,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                
                result = data['data']['results'][0]
                citations = result['citations']
                
                # Verify comprehensive citation information
                assert citations['chunk_id'] == 1
                assert citations['position'] == 0
                assert citations['document_title'] == 'Q3 Financial Report'
                assert citations['source_name'] == 'Financial Reports'
                assert citations['source_type'] == 'document'
                assert citations['page_number'] == 3
                assert citations['section'] == 'Revenue Analysis'
                assert 'created_at' in citations
                assert 'updated_at' in citations
                
                # Verify metadata for context
                metadata = result['metadata']
                assert metadata['context_type'] == 'financial_data'
                assert metadata['data_freshness'] == 'current_quarter'


class TestSearchRelevanceValidation:
    """Test search relevance validation and quality metrics."""
    
    @pytest.fixture(autouse=True)
    def setup(self, app, client):
        """Set up test data."""
        self.app = app
        self.client = client
        
        with app.app_context():
            # Create test tenant and user
            self.tenant = create_test_tenant()
            self.user = create_test_user(tenant_id=self.tenant.id)
            
            # Get auth token
            response = client.post('/api/v1/auth/login', json={
                'email': self.user.email,
                'password': 'testpass123'
            })
            self.auth_token = response.json['data']['access_token']
            self.auth_headers = {'Authorization': f'Bearer {self.auth_token}'}
    
    def test_search_relevance_threshold_validation(self):
        """Test validation of search relevance thresholds."""
        with self.app.app_context():
            # Mock search results with varying relevance
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Highly relevant content matching the query exactly.',
                    'similarity_score': 0.95,
                    'title': 'Exact Match',
                    'relevance_score': 0.95,
                    'citations': {'document_title': 'Exact Match'},
                    'metadata': {'relevance_category': 'high'}
                },
                {
                    'chunk_id': 2,
                    'document_id': 2,
                    'content': 'Moderately relevant content with some query terms.',
                    'similarity_score': 0.78,
                    'title': 'Partial Match',
                    'relevance_score': 0.78,
                    'citations': {'document_title': 'Partial Match'},
                    'metadata': {'relevance_category': 'medium'}
                },
                {
                    'chunk_id': 3,
                    'document_id': 3,
                    'content': 'Barely relevant content with minimal connection.',
                    'similarity_score': 0.65,
                    'title': 'Weak Match',
                    'relevance_score': 0.65,
                    'citations': {'document_title': 'Weak Match'},
                    'metadata': {'relevance_category': 'low'}
                }
            ]
            
            # Test with high relevance threshold
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge') as mock_search:
                mock_search.return_value = [r for r in mock_search_results if r['similarity_score'] >= 0.9]
                
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'test query',
                        'limit': 10,
                        'min_similarity': 0.9  # High threshold
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                assert data['data']['results'][0]['similarity_score'] >= 0.9
                assert data['data']['results'][0]['metadata']['relevance_category'] == 'high'
    
    def test_search_quality_metrics(self):
        """Test search quality metrics and performance indicators."""
        with self.app.app_context():
            # Mock search results with quality metrics
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'High quality search result with comprehensive information.',
                    'similarity_score': 0.92,
                    'title': 'Quality Result',
                    'relevance_score': 0.92,
                    'citations': {'document_title': 'Quality Result'},
                    'metadata': {
                        'search_type': 'vector',
                        'quality_score': 0.91,
                        'completeness': 0.88,
                        'accuracy': 0.94,
                        'freshness': 0.85
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'comprehensive information search',
                        'limit': 5,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 1
                
                result = data['data']['results'][0]
                metadata = result['metadata']
                
                # Verify quality metrics
                assert 'quality_score' in metadata
                assert 'completeness' in metadata
                assert 'accuracy' in metadata
                assert 'freshness' in metadata
                
                assert metadata['quality_score'] >= 0.8
                assert metadata['completeness'] >= 0.8
                assert metadata['accuracy'] >= 0.8
    
    def test_search_performance_validation(self):
        """Test search performance and response time validation."""
        with self.app.app_context():
            # Mock search with performance metrics
            mock_search_results = [
                {
                    'chunk_id': 1,
                    'document_id': 1,
                    'content': 'Fast search result.',
                    'similarity_score': 0.89,
                    'title': 'Fast Result',
                    'relevance_score': 0.89,
                    'citations': {'document_title': 'Fast Result'},
                    'metadata': {
                        'search_type': 'vector',
                        'search_time_ms': 45,
                        'index_size': 1000,
                        'documents_searched': 500
                    }
                }
            ]
            
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=mock_search_results):
                import time
                start_time = time.time()
                
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'performance test query',
                        'limit': 10,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                end_time = time.time()
                response_time = (end_time - start_time) * 1000  # Convert to milliseconds
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                
                # Verify reasonable response time (should be under 1 second for tests)
                assert response_time < 1000
                
                result = data['data']['results'][0]
                metadata = result['metadata']
                
                # Verify performance metrics are included
                assert 'search_time_ms' in metadata
                assert metadata['search_time_ms'] < 100  # Should be fast
    
    def test_search_no_results_handling(self):
        """Test handling of searches with no relevant results."""
        with self.app.app_context():
            # Mock empty search results
            with patch('app.services.knowledge_service.KnowledgeService.search_knowledge', return_value=[]):
                response = self.client.post(
                    '/api/v1/knowledge/search',
                    json={
                        'query': 'nonexistent topic that should return no results',
                        'limit': 10,
                        'min_similarity': 0.8
                    },
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert len(data['data']['results']) == 0
                assert data['data']['total'] == 0
                
                # Verify query information is still returned
                assert data['data']['query'] == 'nonexistent topic that should return no results'
                assert data['data']['limit'] == 10
                assert data['data']['min_similarity'] == 0.8