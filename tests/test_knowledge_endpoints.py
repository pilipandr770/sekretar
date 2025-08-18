"""Tests for knowledge management endpoints."""
import os
import json
import tempfile
from io import BytesIO
from unittest.mock import patch, MagicMock
import pytest
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.knowledge import KnowledgeSource, Document


def create_test_tenant(name="Test Tenant", domain="test.example.com"):
    """Create a test tenant."""
    tenant = Tenant(
        name=name,
        domain=domain,
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


class TestKnowledgeEndpoints:
    """Test knowledge management endpoints."""
    
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
    
    def test_get_knowledge_sources_empty(self):
        """Test getting knowledge sources when none exist."""
        response = self.client.get(
            '/api/v1/knowledge/sources',
            headers=self.auth_headers
        )
        
        assert response.status_code == 200
        data = response.json
        assert data['success'] is True
        assert data['data']['sources'] == []
        assert data['data']['total'] == 0
    
    def test_create_document_source(self):
        """Test creating a document-based knowledge source."""
        source_data = {
            'name': 'Test Documents',
            'source_type': 'document',
            'description': 'Test document source',
            'tags': ['test', 'documents']
        }
        
        response = self.client.post(
            '/api/v1/knowledge/sources',
            json=source_data,
            headers=self.auth_headers
        )
        
        assert response.status_code == 201
        data = response.json
        assert data['success'] is True
        assert data['data']['source']['name'] == 'Test Documents'
        assert data['data']['source']['source_type'] == 'document'
        assert data['data']['source']['status'] == 'pending'
        assert 'test' in data['data']['source']['tags']
    
    def test_create_url_source(self):
        """Test creating a URL-based knowledge source."""
        source_data = {
            'name': 'Test Website',
            'source_type': 'url',
            'url': 'https://example.com',
            'description': 'Test URL source',
            'crawl_frequency': 'weekly',
            'max_depth': 2
        }
        
        response = self.client.post(
            '/api/v1/knowledge/sources',
            json=source_data,
            headers=self.auth_headers
        )
        
        assert response.status_code == 201
        data = response.json
        assert data['success'] is True
        assert data['data']['source']['name'] == 'Test Website'
        assert data['data']['source']['source_type'] == 'url'
        assert data['data']['source']['source_url'] == 'https://example.com'
        assert data['data']['source']['crawl_frequency'] == 'weekly'
        assert data['data']['source']['max_depth'] == 2
    
    def test_create_source_missing_name(self):
        """Test creating source without required name field."""
        source_data = {
            'source_type': 'document'
        }
        
        response = self.client.post(
            '/api/v1/knowledge/sources',
            json=source_data,
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'name' in data['error']['message'].lower()
    
    def test_create_url_source_missing_url(self):
        """Test creating URL source without URL."""
        source_data = {
            'name': 'Test Website',
            'source_type': 'url'
        }
        
        response = self.client.post(
            '/api/v1/knowledge/sources',
            json=source_data,
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'url' in data['error']['message'].lower()
    
    def test_create_source_invalid_type(self):
        """Test creating source with invalid type."""
        source_data = {
            'name': 'Test Source',
            'source_type': 'invalid'
        }
        
        response = self.client.post(
            '/api/v1/knowledge/sources',
            json=source_data,
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'invalid source type' in data['error']['message'].lower()
    
    def test_get_knowledge_source(self):
        """Test getting a specific knowledge source."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Source'
            )
            source.save()
            
            response = self.client.get(
                f'/api/v1/knowledge/sources/{source.id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['source']['id'] == source.id
            assert data['data']['source']['name'] == 'Test Source'
    
    def test_get_nonexistent_source(self):
        """Test getting a non-existent knowledge source."""
        response = self.client.get(
            '/api/v1/knowledge/sources/99999',
            headers=self.auth_headers
        )
        
        assert response.status_code == 404
        data = response.json
        assert data['success'] is False
        assert 'not found' in data['error']['message'].lower()
    
    def test_delete_knowledge_source(self):
        """Test deleting a knowledge source."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Source'
            )
            source.save()
            source_id = source.id
            
            response = self.client.delete(
                f'/api/v1/knowledge/sources/{source_id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['deleted'] is True
            
            # Verify source is deleted
            deleted_source = KnowledgeSource.get_by_id(source_id)
            assert deleted_source is None
    
    def test_upload_document(self):
        """Test uploading a document."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.save()
            
            # Create test file
            test_content = "This is test document content."
            test_file = BytesIO(test_content.encode('utf-8'))
            test_file.name = 'test.txt'
            
            response = self.client.post(
                f'/api/v1/knowledge/sources/{source.id}/upload',
                data={
                    'file': (test_file, 'test.txt', 'text/plain'),
                    'title': 'Test Document'
                },
                headers=self.auth_headers,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 201
            data = response.json
            assert data['success'] is True
            assert data['data']['document']['title'] == 'Test Document'
            assert data['data']['document']['filename'] == 'test.txt'
            assert data['data']['document']['mime_type'] == 'text/plain'
    
    def test_upload_document_no_file(self):
        """Test uploading without providing a file."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.save()
            
            response = self.client.post(
                f'/api/v1/knowledge/sources/{source.id}/upload',
                data={},
                headers=self.auth_headers,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 400
            data = response.json
            assert data['success'] is False
            assert 'no file' in data['error']['message'].lower()
    
    def test_upload_document_invalid_extension(self):
        """Test uploading a file with invalid extension."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.save()
            
            # Create test file with invalid extension
            test_content = "This is test content."
            test_file = BytesIO(test_content.encode('utf-8'))
            test_file.name = 'test.exe'
            
            response = self.client.post(
                f'/api/v1/knowledge/sources/{source.id}/upload',
                data={
                    'file': (test_file, 'test.exe', 'application/octet-stream')
                },
                headers=self.auth_headers,
                content_type='multipart/form-data'
            )
            
            assert response.status_code == 400
            data = response.json
            assert data['success'] is False
            assert 'not allowed' in data['error']['message'].lower()
    
    @patch('requests.get')
    def test_crawl_url(self, mock_get):
        """Test crawling a URL."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_url_source(
                tenant_id=self.tenant.id,
                name='Test Website',
                url='https://example.com'
            )
            source.save()
            
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.text = '<html><body>Test content</body></html>'
            mock_response.headers = {'content-type': 'text/html'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            response = self.client.post(
                f'/api/v1/knowledge/sources/{source.id}/crawl',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['total'] == 1
            assert len(data['data']['documents']) == 1
            
            document = data['data']['documents'][0]
            assert 'example.com' in document['title']
            assert document['url'] == 'https://example.com'
    
    @patch('requests.get')
    def test_crawl_url_with_custom_url(self, mock_get):
        """Test crawling with a custom URL."""
        with self.app.app_context():
            # Create test source
            source = KnowledgeSource.create_url_source(
                tenant_id=self.tenant.id,
                name='Test Website',
                url='https://example.com'
            )
            source.save()
            
            # Mock HTTP response
            mock_response = MagicMock()
            mock_response.text = 'Custom URL content'
            mock_response.headers = {'content-type': 'text/plain'}
            mock_response.raise_for_status.return_value = None
            mock_get.return_value = mock_response
            
            response = self.client.post(
                f'/api/v1/knowledge/sources/{source.id}/crawl',
                json={'url': 'https://custom.com'},
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            
            # Verify custom URL was used
            mock_get.assert_called_once()
            args, kwargs = mock_get.call_args
            assert args[0] == 'https://custom.com'
    
    def test_get_source_documents(self):
        """Test getting documents for a source."""
        with self.app.app_context():
            # Create test source and document
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.save()
            
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Test Document',
                content='Test content'
            )
            document.save()
            
            response = self.client.get(
                f'/api/v1/knowledge/sources/{source.id}/documents',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['total'] == 1
            assert len(data['data']['documents']) == 1
            assert data['data']['documents'][0]['title'] == 'Test Document'
    
    def test_get_document(self):
        """Test getting a specific document."""
        with self.app.app_context():
            # Create test source and document
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.save()
            
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Test Document',
                content='Full document content here'
            )
            document.save()
            
            response = self.client.get(
                f'/api/v1/knowledge/documents/{document.id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['document']['title'] == 'Test Document'
            assert data['data']['document']['content'] == 'Full document content here'
    
    def test_delete_document(self):
        """Test deleting a document."""
        with self.app.app_context():
            # Create test source and document
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.save()
            
            document = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Test Document',
                content='Test content'
            )
            document.save()
            document_id = document.id
            
            response = self.client.delete(
                f'/api/v1/knowledge/documents/{document_id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['deleted'] is True
            
            # Verify document is deleted
            deleted_document = Document.get_by_id(document_id)
            assert deleted_document is None
    
    def test_search_knowledge(self):
        """Test searching the knowledge base."""
        with self.app.app_context():
            # Create test source and documents
            source = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Test Documents'
            )
            source.mark_as_completed()
            source.save()
            
            # Create documents with different content
            doc1 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='Python Programming Guide',
                content='Learn Python programming with examples'
            )
            doc1.save()
            
            doc2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source.id,
                title='JavaScript Tutorial',
                content='JavaScript basics and advanced concepts'
            )
            doc2.save()
            
            # Search for Python
            response = self.client.post(
                '/api/v1/knowledge/search',
                json={
                    'query': 'Python programming',
                    'limit': 10,
                    'min_similarity': 0.1
                },
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            assert data['data']['query'] == 'Python programming'
            assert len(data['data']['results']) >= 1
            
            # First result should be the Python document
            first_result = data['data']['results'][0]
            assert 'Python' in first_result['title']
            assert first_result['relevance_score'] > 0
            assert 'citations' in first_result
    
    def test_search_knowledge_empty_query(self):
        """Test searching with empty query."""
        response = self.client.post(
            '/api/v1/knowledge/search',
            json={'query': '   '},
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'empty' in data['error']['message'].lower()
    
    def test_search_knowledge_invalid_limit(self):
        """Test searching with invalid limit."""
        response = self.client.post(
            '/api/v1/knowledge/search',
            json={
                'query': 'test',
                'limit': 100  # Too high
            },
            headers=self.auth_headers
        )
        
        assert response.status_code == 400
        data = response.json
        assert data['success'] is False
        assert 'limit' in data['error']['message'].lower()
    
    def test_get_knowledge_stats(self):
        """Test getting knowledge base statistics."""
        with self.app.app_context():
            # Create test data
            source1 = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Completed Source'
            )
            source1.mark_as_completed()
            source1.save()
            
            source2 = KnowledgeSource.create_document_source(
                tenant_id=self.tenant.id,
                name='Pending Source'
            )
            source2.save()  # Status remains 'pending'
            
            # Create documents
            doc1 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source1.id,
                title='Document 1',
                content='Content 1',
                token_count=100
            )
            doc1.save()
            
            doc2 = Document.create(
                tenant_id=self.tenant.id,
                source_id=source1.id,
                title='Document 2',
                content='Content 2',
                token_count=150
            )
            doc2.save()
            
            response = self.client.get(
                '/api/v1/knowledge/stats',
                headers=self.auth_headers
            )
            
            assert response.status_code == 200
            data = response.json
            assert data['success'] is True
            
            stats = data['data']
            assert stats['sources']['total'] == 2
            assert stats['sources']['active'] == 1
            assert stats['sources']['pending'] == 1
            assert stats['documents']['total'] == 2
            assert stats['documents']['total_tokens'] == 250
    
    def test_unauthorized_access(self):
        """Test accessing endpoints without authentication."""
        response = self.client.get('/api/v1/knowledge/sources')
        assert response.status_code == 401
    
    def test_cross_tenant_access_prevention(self):
        """Test that users cannot access other tenants' knowledge sources."""
        with self.app.app_context():
            # Create another tenant and source
            other_tenant = create_test_tenant(name='Other Tenant')
            other_source = KnowledgeSource.create_document_source(
                tenant_id=other_tenant.id,
                name='Other Tenant Source'
            )
            other_source.save()
            
            # Try to access other tenant's source
            response = self.client.get(
                f'/api/v1/knowledge/sources/{other_source.id}',
                headers=self.auth_headers
            )
            
            assert response.status_code == 404
            data = response.json
            assert data['success'] is False
            assert 'not found' in data['error']['message'].lower()