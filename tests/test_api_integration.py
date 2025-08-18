"""Integration tests for API endpoints with real Flask application context."""
import pytest
import json
from unittest.mock import patch
from app import create_app
from app.services.health_service import HealthCheckResult, OverallHealthResult


class TestAPIIntegration:
    """Integration tests for API endpoints with full Flask application context."""
    
    def test_welcome_endpoint_with_real_flask_context(self, client):
        """Test welcome endpoint with real Flask application context."""
        response = client.get('/')
        
        # Verify HTTP status and headers
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert 'Content-Length' in response.headers
        
        # Verify JSON response format
        data = response.get_json()
        assert isinstance(data, dict)
        
        # Verify required fields are present
        required_fields = ['message', 'version', 'environment', 'endpoints', 'timestamp']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types and values
        assert isinstance(data['message'], str)
        assert data['message'] == "Welcome to AI Secretary API"
        assert isinstance(data['version'], str)
        assert isinstance(data['environment'], str)
        assert isinstance(data['endpoints'], dict)
        assert isinstance(data['timestamp'], str)
        
        # Verify endpoints structure
        endpoints = data['endpoints']
        expected_endpoints = ['health', 'version', 'auth', 'docs']
        for endpoint in expected_endpoints:
            assert endpoint in endpoints
            assert isinstance(endpoints[endpoint], str)
            assert endpoints[endpoint].startswith('/api/v1/') or endpoints[endpoint] == '/api/v1/docs'
        
        # Verify timestamp format (ISO-8601 with Z suffix)
        assert data['timestamp'].endswith('Z')
        
        # Verify environment is one of expected values
        assert data['environment'] in ['development', 'testing', 'production']
    
    def test_health_endpoint_with_real_flask_context(self, client):
        """Test health endpoint with real Flask application context."""
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            # Mock healthy response
            mock_health.return_value = OverallHealthResult(
                status="healthy",
                checks={
                    'database': HealthCheckResult(
                        status="healthy",
                        response_time_ms=15
                    ),
                    'redis': HealthCheckResult(
                        status="healthy",
                        response_time_ms=5
                    )
                },
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            
            # Verify HTTP status and headers
            assert response.status_code == 200
            assert response.content_type == 'application/json'
            assert 'Content-Length' in response.headers
            
            # Verify JSON response format
            data = response.get_json()
            assert isinstance(data, dict)
            
            # Verify required fields
            required_fields = ['status', 'timestamp', 'version', 'checks']
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"
            
            # Verify data structure
            assert data['status'] == "healthy"
            assert isinstance(data['checks'], dict)
            assert 'database' in data['checks']
            assert 'redis' in data['checks']
            
            # Verify individual check structure
            for service_name, check_data in data['checks'].items():
                assert 'status' in check_data
                assert 'response_time_ms' in check_data
                assert isinstance(check_data['status'], str)
                assert isinstance(check_data['response_time_ms'], int)
    
    def test_version_endpoint_with_real_flask_context(self, client):
        """Test version endpoint with real Flask application context."""
        response = client.get('/api/v1/version')
        
        # Verify HTTP status and headers
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        assert 'Content-Length' in response.headers
        
        # Verify JSON response format
        data = response.get_json()
        assert isinstance(data, dict)
        
        # Verify required fields
        required_fields = ['version', 'environment', 'python_version', 'flask_version']
        for field in required_fields:
            assert field in data, f"Missing required field: {field}"
        
        # Verify data types and formats
        assert isinstance(data['version'], str)
        assert isinstance(data['environment'], str)
        assert isinstance(data['python_version'], str)
        assert isinstance(data['flask_version'], str)
        
        # Verify version formats (should contain dots)
        assert '.' in data['python_version']
        assert '.' in data['flask_version']
        
        # Verify environment
        assert data['environment'] in ['development', 'testing', 'production']
        
        # Verify build_date field handling
        if 'build_date' in data:
            assert isinstance(data['build_date'], str) or data['build_date'] is None
    
    def test_endpoints_http_headers(self, client):
        """Test that all endpoints return correct HTTP headers."""
        endpoints = [
            '/',
            '/api/v1/health',
            '/api/v1/version'
        ]
        
        for endpoint in endpoints:
            if endpoint == '/api/v1/health':
                # Mock health service for health endpoint
                with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
                    mock_health.return_value = OverallHealthResult(
                        status="healthy",
                        checks={'database': HealthCheckResult(status="healthy", response_time_ms=10)},
                        timestamp="2025-08-10T22:48:26Z"
                    )
                    response = client.get(endpoint)
            else:
                response = client.get(endpoint)
            
            # Verify common headers
            assert response.content_type == 'application/json'
            assert 'Content-Length' in response.headers
            assert int(response.headers['Content-Length']) > 0
            
            # Verify response is valid JSON
            data = response.get_json()
            assert data is not None
            assert isinstance(data, dict)
    
    def test_cors_functionality_if_enabled(self, client, app):
        """Test CORS functionality if enabled."""
        # Check if CORS is configured
        cors_origins = app.config.get('CORS_ORIGINS', [])
        
        if cors_origins:
            # Test preflight request
            response = client.options('/', headers={
                'Origin': cors_origins[0],
                'Access-Control-Request-Method': 'GET',
                'Access-Control-Request-Headers': 'Content-Type'
            })
            
            # CORS preflight should return 200
            assert response.status_code == 200
            
            # Test actual request with CORS headers
            response = client.get('/', headers={
                'Origin': cors_origins[0]
            })
            
            assert response.status_code == 200
            
            # Check for CORS headers in response (if CORS is properly configured)
            # Note: The actual CORS headers depend on Flask-CORS configuration
            # This test verifies the request succeeds with Origin header
            
        else:
            # If CORS is not configured, test that requests still work
            response = client.get('/')
            assert response.status_code == 200
    
    def test_endpoints_with_different_http_methods(self, client):
        """Test endpoints respond correctly to different HTTP methods."""
        endpoints = [
            '/',
            '/api/v1/health',
            '/api/v1/version'
        ]
        
        for endpoint in endpoints:
            # Test GET (should work)
            if endpoint == '/api/v1/health':
                with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
                    mock_health.return_value = OverallHealthResult(
                        status="healthy",
                        checks={'database': HealthCheckResult(status="healthy", response_time_ms=10)},
                        timestamp="2025-08-10T22:48:26Z"
                    )
                    response = client.get(endpoint)
                    assert response.status_code == 200
            else:
                response = client.get(endpoint)
                assert response.status_code == 200
            
            # Test POST (should return 405 Method Not Allowed)
            response = client.post(endpoint)
            assert response.status_code == 405
            
            # Test PUT (should return 405 Method Not Allowed)
            response = client.put(endpoint)
            assert response.status_code == 405
            
            # Test DELETE (should return 405 Method Not Allowed)
            response = client.delete(endpoint)
            assert response.status_code == 405
    
    def test_health_endpoint_error_scenarios_integration(self, client):
        """Test health endpoint error scenarios in integration context."""
        # Test when health service raises exception
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.side_effect = Exception("Service unavailable")
            
            response = client.get('/api/v1/health')
            
            assert response.status_code == 503
            assert response.content_type == 'application/json'
            
            data = response.get_json()
            assert 'error' in data
            assert data['success'] is False
            assert data['error']['code'] == "HEALTH_CHECK_FAILED"
    
    def test_database_unhealthy_returns_503(self, client):
        """Test that database unhealthy status returns 503 status code."""
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.return_value = OverallHealthResult(
                status="unhealthy",
                checks={
                    'database': HealthCheckResult(
                        status="unhealthy",
                        response_time_ms=None,
                        error="Connection timeout"
                    ),
                    'redis': HealthCheckResult(
                        status="healthy",
                        response_time_ms=5
                    )
                },
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            
            # Database failure should return 503 per requirement 1.4
            assert response.status_code == 503
            assert response.content_type == 'application/json'
            
            data = response.get_json()
            assert data['status'] == "unhealthy"
            assert data['checks']['database']['status'] == "unhealthy"
            assert data['checks']['database']['error'] == "Connection timeout"
    
    def test_redis_unhealthy_returns_200(self, client):
        """Test that Redis unhealthy alone returns 200 status code."""
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.return_value = OverallHealthResult(
                status="healthy",  # Overall still healthy per requirement 1.5
                checks={
                    'database': HealthCheckResult(
                        status="healthy",
                        response_time_ms=12
                    ),
                    'redis': HealthCheckResult(
                        status="unhealthy",
                        response_time_ms=None,
                        error="Redis connection failed"
                    )
                },
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            
            # Redis failure alone should return 200 per requirement 1.5
            assert response.status_code == 200
            assert response.content_type == 'application/json'
            
            data = response.get_json()
            assert data['status'] == "healthy"
            assert data['checks']['redis']['status'] == "unhealthy"
            assert data['checks']['redis']['error'] == "Redis connection failed"
    
    def test_json_response_formats_consistency(self, client):
        """Test that all endpoints return consistent JSON response formats."""
        # Test welcome endpoint
        response = client.get('/')
        assert response.status_code == 200
        welcome_data = response.get_json()
        
        # Welcome should have timestamp
        assert 'timestamp' in welcome_data
        assert isinstance(welcome_data['timestamp'], str)
        
        # Test version endpoint
        response = client.get('/api/v1/version')
        assert response.status_code == 200
        version_data = response.get_json()
        
        # Version endpoint structure
        assert isinstance(version_data, dict)
        assert 'version' in version_data
        
        # Test health endpoint
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.return_value = OverallHealthResult(
                status="healthy",
                checks={'database': HealthCheckResult(status="healthy", response_time_ms=10)},
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            assert response.status_code == 200
            health_data = response.get_json()
            
            # Health should have timestamp
            assert 'timestamp' in health_data
            assert isinstance(health_data['timestamp'], str)
    
    def test_endpoints_with_custom_configuration(self, app, client):
        """Test endpoints with custom application configuration."""
        with app.app_context():
            # Set custom configuration
            original_version = app.config.get('API_VERSION')
            original_env = app.config.get('FLASK_ENV')
            original_build_date = app.config.get('BUILD_DATE')
            
            app.config['API_VERSION'] = '2.5.0'
            app.config['FLASK_ENV'] = 'production'
            app.config['BUILD_DATE'] = '2025-08-10T20:00:00Z'
            
            try:
                # Test welcome endpoint with custom config
                response = client.get('/')
                assert response.status_code == 200
                data = response.get_json()
                assert data['version'] == '2.5.0'
                assert data['environment'] == 'production'
                
                # Test version endpoint with custom config
                response = client.get('/api/v1/version')
                assert response.status_code == 200
                data = response.get_json()
                assert data['version'] == '2.5.0'
                assert data['environment'] == 'production'
                assert data['build_date'] == '2025-08-10T20:00:00Z'
                
                # Test health endpoint with custom config
                with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
                    mock_health.return_value = OverallHealthResult(
                        status="healthy",
                        checks={'database': HealthCheckResult(status="healthy", response_time_ms=10)},
                        timestamp="2025-08-10T22:48:26Z"
                    )
                    
                    response = client.get('/api/v1/health')
                    assert response.status_code == 200
                    data = response.get_json()
                    assert data['version'] == '2.5.0'
                    
            finally:
                # Restore original configuration
                if original_version:
                    app.config['API_VERSION'] = original_version
                if original_env:
                    app.config['FLASK_ENV'] = original_env
                if original_build_date:
                    app.config['BUILD_DATE'] = original_build_date
    
    def test_endpoints_performance_and_response_times(self, client):
        """Test that endpoints respond within reasonable time limits."""
        import time
        
        endpoints = [
            '/',
            '/api/v1/version'
        ]
        
        for endpoint in endpoints:
            start_time = time.time()
            response = client.get(endpoint)
            end_time = time.time()
            
            response_time = end_time - start_time
            
            # Endpoints should respond quickly (within 1 second for integration tests)
            assert response_time < 1.0, f"Endpoint {endpoint} took {response_time:.3f}s to respond"
            assert response.status_code == 200
        
        # Test health endpoint with mocked service
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.return_value = OverallHealthResult(
                status="healthy",
                checks={'database': HealthCheckResult(status="healthy", response_time_ms=10)},
                timestamp="2025-08-10T22:48:26Z"
            )
            
            start_time = time.time()
            response = client.get('/api/v1/health')
            end_time = time.time()
            
            response_time = end_time - start_time
            assert response_time < 1.0, f"Health endpoint took {response_time:.3f}s to respond"
            assert response.status_code == 200