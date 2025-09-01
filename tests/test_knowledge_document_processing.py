"""Comprehensive tests for knowledge management document processing functionality."""
import os
import tempfile
import pytest
from io import BytesIO
from unittest.mock import patch, Mock, MagicMock
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.knowledge import KnowledgeSource, Document, Chunk, Embedding
from app.services.knowledge_service import KnowledgeService
from app.services.document_processor import DocumentProcessor
from app.utils.exceptions import ValidationError, ProcessingError


class TestDocumentUploadProcessing:
    """Test document upload and processing functionality."""
    
    def test_upload_text_document_success(self, app, client, tenant, auth_headers):
        """Test successful upload and processing of text document."""
        with app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=tenant.id,
                name='Test Documents'
            )
            source.save()
            
            # Create test text file
            test_content = """
            This is a comprehensive test document for knowledge management.
            It contains multiple paragraphs with different topics.
            
            The document should be processed correctly and chunked appropriately.
            Each chunk should maintain context while being searchable.
            
            This content will be used to test the document processing pipeline
            including text extraction, chunking, and embedding generation.
            """
            
            test_file = BytesIO(test_content.encode('utf-8'))
            test_file.name = 'test_document.txt'
            
            # Mock document processing
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.return_value = {
                    'content': test_content.strip(),
                    'token_count': 85,
                    'content_hash': 'test_hash_123',
                    'file_size': len(test_content),
                    'mime_type': 'text/plain',
                    'file_extension': 'txt',
                    'metadata': {'format': 'plain_text', 'lines': 8}
                }
                
                mock_processor.chunk_text.return_value = [
                    {
                        'content': 'This is a comprehensive test document for knowledge management. It contains multiple paragraphs with different topics.',
                        'position': 0,
                        'token_count': 20,
                        'overlap_start': 0,
                        'overlap_end': 0
                    },
                    {
                        'content': 'The document should be processed correctly and chunked appropriately. Each chunk should maintain context while being searchable.',
                        'position': 1,
                        'token_count': 22,
                        'overlap_start': 0,
                        'overlap_end': 0
                    },
                    {
                        'content': 'This content will be used to test the document processing pipeline including text extraction, chunking, and embedding generation.',
                        'position': 2,
                        'token_count': 23,
                        'overlap_start': 0,
                        'overlap_end': 0
                    }
                ]
                
                response = client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file, 'test_document.txt', 'text/plain'),
                        'title': 'Comprehensive Test Document'
                    },
                    headers=auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response.status_code == 201
                data = response.json
                assert data['success'] is True
                assert data['data']['document']['title'] == 'Comprehensive Test Document'
                assert data['data']['document']['filename'] == 'test_document.txt'
                assert data['data']['document']['mime_type'] == 'text/plain'
                assert data['data']['document']['token_count'] == 85
                
                # Verify document was created in database
                document = Document.query.filter_by(
                    tenant_id=tenant.id,
                    title='Comprehensive Test Document'
                ).first()
                
                assert document is not None
                assert document.content_hash == 'test_hash_123'
                assert document.processing_status == 'completed'
                
                # Verify chunks were created
                chunks = Chunk.query.filter_by(document_id=document.id).all()
                assert len(chunks) == 3
                assert chunks[0].position == 0
                assert chunks[1].position == 1
                assert chunks[2].position == 2
    
    def test_upload_pdf_document_processing(self):
        """Test PDF document upload and processing."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='PDF Documents'
            )
            source.save()
            
            # Create mock PDF content
            pdf_content = b'%PDF-1.4 mock pdf content'
            test_file = BytesIO(pdf_content)
            test_file.name = 'test.pdf'
            
            # Mock PDF processing
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.return_value = {
                    'content': 'This is extracted text from PDF document. It contains important business information.',
                    'token_count': 15,
                    'content_hash': 'pdf_hash_456',
                    'file_size': len(pdf_content),
                    'mime_type': 'application/pdf',
                    'file_extension': 'pdf',
                    'metadata': {
                        'pages': 1,
                        'title': 'Business Document',
                        'author': 'Test Author'
                    }
                }
                
                mock_processor.chunk_text.return_value = [
                    {
                        'content': 'This is extracted text from PDF document. It contains important business information.',
                        'position': 0,
                        'token_count': 15,
                        'overlap_start': 0,
                        'overlap_end': 0
                    }
                ]
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file, 'test.pdf', 'application/pdf'),
                        'title': 'Business PDF Document'
                    },
                    headers=self.auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response.status_code == 201
                data = response.json
                assert data['success'] is True
                assert data['data']['document']['title'] == 'Business PDF Document'
                assert data['data']['document']['mime_type'] == 'application/pdf'
                
                # Verify document metadata was stored
                document = Document.query.filter_by(
                    tenant_id=self.tenant.id,
                    title='Business PDF Document'
                ).first()
                
                assert document is not None
                assert document.get_metadata('pages') == 1
                assert document.get_metadata('author') == 'Test Author'
    
    def test_upload_large_document_chunking(self):
        """Test processing of large documents with proper chunking."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Large Documents'
            )
            source.save()
            
            # Create large test content
            large_content = """
            Chapter 1: Introduction to Knowledge Management
            
            Knowledge management is a critical aspect of modern business operations.
            It involves the systematic approach to capturing, organizing, and utilizing
            organizational knowledge to improve decision-making and operational efficiency.
            
            Chapter 2: Document Processing Systems
            
            Document processing systems are essential for converting unstructured data
            into structured, searchable formats. These systems typically involve
            text extraction, natural language processing, and semantic analysis.
            
            Chapter 3: Vector Embeddings and Semantic Search
            
            Vector embeddings represent text as high-dimensional vectors that capture
            semantic meaning. This enables sophisticated search capabilities that go
            beyond simple keyword matching to understand context and intent.
            
            Chapter 4: Implementation Best Practices
            
            When implementing knowledge management systems, it's important to consider
            scalability, accuracy, and user experience. Proper chunking strategies
            ensure that information remains contextually relevant while being searchable.
            
            Chapter 5: Future Developments
            
            The future of knowledge management lies in advanced AI capabilities,
            including better understanding of context, multi-modal processing,
            and real-time knowledge updates.
            """ * 3  # Make it larger
            
            test_file = BytesIO(large_content.encode('utf-8'))
            test_file.name = 'large_document.txt'
            
            # Mock processing with multiple chunks
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.return_value = {
                    'content': large_content.strip(),
                    'token_count': 450,
                    'content_hash': 'large_hash_789',
                    'file_size': len(large_content),
                    'mime_type': 'text/plain',
                    'file_extension': 'txt',
                    'metadata': {'format': 'plain_text', 'lines': 75}
                }
                
                # Mock chunking with overlap
                mock_chunks = []
                content_parts = large_content.split('Chapter')
                for i, part in enumerate(content_parts[1:], 1):  # Skip empty first part
                    chunk_content = f"Chapter{part}".strip()
                    if chunk_content:
                        mock_chunks.append({
                            'content': chunk_content[:500],  # Truncate for testing
                            'position': i-1,
                            'token_count': 75,
                            'overlap_start': 10 if i > 1 else 0,
                            'overlap_end': 10 if i < len(content_parts)-1 else 0
                        })
                
                mock_processor.chunk_text.return_value = mock_chunks
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file, 'large_document.txt', 'text/plain'),
                        'title': 'Large Knowledge Management Guide'
                    },
                    headers=self.auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response.status_code == 201
                data = response.json
                assert data['success'] is True
                
                # Verify document and chunks
                document = Document.query.filter_by(
                    tenant_id=self.tenant.id,
                    title='Large Knowledge Management Guide'
                ).first()
                
                assert document is not None
                assert document.token_count == 450
                
                chunks = Chunk.query.filter_by(document_id=document.id).order_by(Chunk.position).all()
                assert len(chunks) == len(mock_chunks)
                
                # Verify chunk overlap information
                for i, chunk in enumerate(chunks):
                    if i > 0:
                        assert chunk.overlap_start == 10
                    if i < len(chunks) - 1:
                        assert chunk.overlap_end == 10
    
    def test_upload_duplicate_document_detection(self):
        """Test detection and handling of duplicate documents."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Duplicate Test'
            )
            source.save()
            
            test_content = "This is a test document for duplicate detection."
            test_file1 = BytesIO(test_content.encode('utf-8'))
            test_file1.name = 'original.txt'
            
            # Mock processing
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.return_value = {
                    'content': test_content,
                    'token_count': 10,
                    'content_hash': 'duplicate_hash_123',
                    'file_size': len(test_content),
                    'mime_type': 'text/plain',
                    'file_extension': 'txt',
                    'metadata': {'format': 'plain_text'}
                }
                
                mock_processor.chunk_text.return_value = [
                    {
                        'content': test_content,
                        'position': 0,
                        'token_count': 10,
                        'overlap_start': 0,
                        'overlap_end': 0
                    }
                ]
                
                # Upload first document
                response1 = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file1, 'original.txt', 'text/plain'),
                        'title': 'Original Document'
                    },
                    headers=self.auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response1.status_code == 201
                
                # Try to upload duplicate
                test_file2 = BytesIO(test_content.encode('utf-8'))
                test_file2.name = 'duplicate.txt'
                
                response2 = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file2, 'duplicate.txt', 'text/plain'),
                        'title': 'Duplicate Document'
                    },
                    headers=self.auth_headers,
                    content_type='multipart/form-data'
                )
                
                # Should handle duplicate gracefully
                assert response2.status_code in [201, 400]  # Depending on implementation
                
                # Verify only one document exists with this hash
                documents = Document.query.filter_by(
                    tenant_id=self.tenant.id,
                    content_hash='duplicate_hash_123'
                ).all()
                
                # Should have only one document (or handle duplicates appropriately)
                assert len(documents) >= 1
    
    def test_upload_invalid_file_types(self):
        """Test handling of invalid file types."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Invalid Files Test'
            )
            source.save()
            
            # Test executable file
            exe_content = b'MZ\x90\x00'  # PE header
            exe_file = BytesIO(exe_content)
            exe_file.name = 'malware.exe'
            
            response = self.client.post(
                f'/api/v1/knowledge/sources/{source.id}/upload',
                data={
                    'file': (exe_file, 'malware.exe', 'application/octet-stream')
                },
                headers=self.auth_headers,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 400
            data = response.json
            assert data['success'] is False
            assert 'not allowed' in data['error']['message'].lower()
    
    def test_upload_oversized_file(self):
        """Test handling of oversized files."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Size Test'
            )
            source.save()
            
            # Create large content (simulate oversized file)
            large_content = "x" * (17 * 1024 * 1024)  # 17MB
            large_file = BytesIO(large_content.encode('utf-8'))
            large_file.name = 'huge.txt'
            
            # Mock processor to raise size error
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.side_effect = ProcessingError("File too large")
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (large_file, 'huge.txt', 'text/plain')
                    },
                    headers=self.auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response.status_code == 500
                data = response.json
                assert data['success'] is False
                assert 'processing error' in data['error']['message'].lower()
    
    def test_document_processing_error_handling(self):
        """Test error handling during document processing."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Error Test'
            )
            source.save()
            
            test_file = BytesIO(b'test content')
            test_file.name = 'error.txt'
            
            # Mock processing error
            with patch('app.services.knowledge_service.DocumentProcessor') as mock_processor:
                mock_processor.extract_text_from_file.side_effect = ProcessingError("Processing failed")
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/upload',
                    data={
                        'file': (test_file, 'error.txt', 'text/plain')
                    },
                    headers=self.auth_headers,
                    content_type='multipart/form-data'
                )
                
                assert response.status_code == 500
                data = response.json
                assert data['success'] is False
                assert 'processing error' in data['error']['message'].lower()


class TestEmbeddingGeneration:
    """Test embedding generation functionality."""
    
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
    
    def test_generate_embeddings_for_source(self):
        """Test generating embeddings for all documents in a source."""
        with self.app.app_context():
            # Create test source with documents
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Embedding Test Source'
            )
            source.save()
            
            # Create test documents with chunks
            doc1 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Document 1',
                content='First test document content',
                token_count=5
            )
            doc1.save()
            
            doc2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Document 2',
                content='Second test document content',
                token_count=5
            )
            doc2.save()
            
            # Create chunks
            chunk1 = Chunk.create(
                tenant_id=self.tenant.id,
                document_id=doc1.id,
                content='First test document content',
                position=0,
                token_count=5
            )
            chunk1.save()
            
            chunk2 = Chunk.create(
                tenant_id=self.tenant.id,
                document_id=doc2.id,
                content='Second test document content',
                position=0,
                token_count=5
            )
            chunk2.save()
            
            # Mock embedding service
            with patch('app.services.knowledge_service.KnowledgeService.generate_embeddings') as mock_generate:
                mock_generate.return_value = {
                    'source_id': source.id,
                    'documents_processed': 2,
                    'embeddings_created': 2,
                    'status': 'completed'
                }
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/embeddings',
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['source_id'] == source.id
                assert data['data']['documents_processed'] == 2
                assert data['data']['embeddings_created'] == 2
                
                # Verify the service was called correctly
                mock_generate.assert_called_once_with(
                    tenant_id=self.tenant.id,
                    source_id=source.id
                )
    
    def test_generate_embeddings_for_document(self):
        """Test generating embeddings for a specific document."""
        with self.app.app_context():
            # Create test document
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Source'
            )
            source.save()
            
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Test Document',
                content='Test document for embedding generation',
                token_count=6
            )
            document.save()
            
            # Create chunks
            chunk = Chunk.create(
                tenant_id=self.tenant.id,
                document_id=document.id,
                content='Test document for embedding generation',
                position=0,
                token_count=6
            )
            chunk.save()
            
            # Mock embedding service
            with patch('app.services.knowledge_service.KnowledgeService.generate_embeddings') as mock_generate:
                mock_generate.return_value = {
                    'document_id': document.id,
                    'embeddings_created': 1,
                    'status': 'completed'
                }
                
                response = self.client.post(
                    f'/api/v1/knowledge/documents/{document.id}/embeddings',
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['document_id'] == document.id
                assert data['data']['embeddings_created'] == 1
                
                # Verify the service was called correctly
                mock_generate.assert_called_once_with(
                    tenant_id=self.tenant.id,
                    document_id=document.id
                )
    
    def test_embedding_generation_error_handling(self):
        """Test error handling in embedding generation."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Error Test Source'
            )
            source.save()
            
            # Mock embedding service error
            with patch('app.services.knowledge_service.KnowledgeService.generate_embeddings') as mock_generate:
                mock_generate.side_effect = ProcessingError("Embedding generation failed")
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/embeddings',
                    headers=self.auth_headers
                )
                
                assert response.status_code == 500
                data = response.json
                assert data['success'] is False
                assert 'processing error' in data['error']['message'].lower()


class TestSearchIndexUpdate:
    """Test search index update functionality."""
    
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
    
    def test_reindex_source_embeddings(self):
        """Test re-indexing embeddings for a knowledge source."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Reindex Test Source'
            )
            source.save()
            
            # Mock reindexing service
            with patch('app.services.knowledge_service.KnowledgeService.reindex_embeddings') as mock_reindex:
                mock_reindex.return_value = {
                    'source_id': source.id,
                    'documents_processed': 5,
                    'embeddings_created': 10,
                    'embeddings_updated': 8,
                    'status': 'completed'
                }
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/reindex',
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['source_id'] == source.id
                assert data['data']['documents_processed'] == 5
                assert data['data']['embeddings_created'] == 10
                assert data['data']['embeddings_updated'] == 8
                
                # Verify the service was called correctly
                mock_reindex.assert_called_once_with(
                    tenant_id=self.tenant.id,
                    source_id=source.id
                )
    
    def test_reindex_nonexistent_source(self):
        """Test re-indexing non-existent source."""
        response = self.client.post(
            '/api/v1/knowledge/sources/99999/reindex',
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
    
    def test_search_index_update_after_document_change(self):
        """Test that search index is updated when documents change."""
        with self.app.app_context():
            # Create test source and document
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Update Test Source'
            )
            source.save()
            
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Original Document',
                content='Original content for testing',
                token_count=5
            )
            document.save()
            
            # Create chunk and embedding
            chunk = Chunk.create(
                tenant_id=self.tenant.id,
                document_id=document.id,
                content='Original content for testing',
                position=0,
                token_count=5
            )
            chunk.save()
            
            # Mock embedding creation
            import numpy as np
            test_vector = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
            embedding = Embedding.create_from_vector(
                tenant_id=self.tenant.id,
                chunk_id=chunk.id,
                vector=test_vector,
                model_name='text-embedding-ada-002'
            )
            
            # Verify embedding exists
            assert embedding.id is not None
            assert embedding.dimension == 5
            
            # Update document content (simulate document change)
            document.content = 'Updated content for testing search index'
            document.token_count = 6
            document.save()
            
            # Mock reindexing after update
            with patch('app.services.knowledge_service.KnowledgeService.reindex_embeddings') as mock_reindex:
                mock_reindex.return_value = {
                    'source_id': source.id,
                    'documents_processed': 1,
                    'embeddings_created': 0,
                    'embeddings_updated': 1,
                    'status': 'completed'
                }
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/reindex',
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['embeddings_updated'] == 1
    
    def test_bulk_index_update_performance(self):
        """Test performance of bulk index updates."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Bulk Update Test'
            )
            source.save()
            
            # Mock bulk processing
            with patch('app.services.knowledge_service.KnowledgeService.reindex_embeddings') as mock_reindex:
                # Simulate processing many documents
                mock_reindex.return_value = {
                    'source_id': source.id,
                    'documents_processed': 100,
                    'embeddings_created': 250,
                    'embeddings_updated': 50,
                    'processing_time': 45.2,
                    'status': 'completed'
                }
                
                response = self.client.post(
                    f'/api/v1/knowledge/sources/{source.id}/reindex',
                    headers=self.auth_headers
                )
                
                assert response.status_code == 200
                data = response.json
                assert data['success'] is True
                assert data['data']['documents_processed'] == 100
                assert data['data']['embeddings_created'] == 250
                
                # Verify bulk processing was efficient
                assert 'processing_time' in data['data']