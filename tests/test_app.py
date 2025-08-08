"""Test application factory and basic functionality."""
import pytest
from app import create_app


def test_config():
    """Test application configuration."""
    assert not create_app().testing
    assert create_app('testing').testing


def test_health_check(client):
    """Test health check endpoint."""
    response = client.get('/api/v1/health')
    assert response.status_code == 200
    
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['service'] == 'ai-secretary-api'


def test_status_endpoint(client):
    """Test status endpoint."""
    response = client.get('/api/v1/status')
    assert response.status_code == 200
    
    data = response.get_json()
    assert data['status'] == 'operational'
    assert 'components' in data