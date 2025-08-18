"""Health check smoke tests."""
import pytest
from app import create_app


def test_health_endpoint_structure(client):
    """Test health endpoint returns correct structure."""
    response = client.get('/api/v1/health')
    
    assert response.status_code == 200
    
    data = response.get_json()
    assert 'status' in data
    assert 'service' in data
    assert 'version' in data
    assert 'components' in data
    
    # Check components
    components = data['components']
    assert 'database' in components
    assert 'redis' in components


def test_health_endpoint_with_app_context():
    """Test health endpoint with full application context."""
    app = create_app('testing')
    
    with app.test_client() as client:
        response = client.get('/api/v1/health')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['service'] == 'ai-secretary-api'


def test_status_endpoint(client):
    """Test status endpoint."""
    response = client.get('/api/v1/status')
    
    assert response.status_code == 200
    
    data = response.get_json()
    assert data['success'] is True
    assert 'data' in data


def test_languages_endpoint(client):
    """Test languages endpoint."""
    response = client.get('/api/v1/languages')
    
    assert response.status_code == 200
    
    data = response.get_json()
    assert data['success'] is True
    assert 'languages' in data['data']
    
    languages = data['data']['languages']
    assert 'en' in languages
    assert 'de' in languages
    assert 'uk' in languages


class TestHealthIntegration:
    """Integration tests for health endpoints."""
    
    def test_health_with_database_connection(self, app):
        """Test health check with actual database connection."""
        with app.app_context():
            from app import db
            
            # This should not raise an exception
            db.session.execute('SELECT 1')
            
            with app.test_client() as client:
                response = client.get('/api/v1/health')
                data = response.get_json()
                
                # Database should be healthy in test environment
                assert data['components']['database'] == 'healthy'
    
    def test_application_startup(self, app):
        """Test that application starts up correctly."""
        assert app is not None
        assert app.config['TESTING'] is True
        
        # Test that we can create a test client
        with app.test_client() as client:
            response = client.get('/api/v1/health')
            assert response.status_code == 200


# Smoke test for local development
def test_local_server_smoke():
    """Smoke test for local development server."""
    # This test is skipped since it requires external requests library
    # and a running server. Integration tests cover this functionality.
    pytest.skip("Smoke test requires running server and requests library")