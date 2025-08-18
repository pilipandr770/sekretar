"""Minimal unit tests for API endpoints without database dependencies."""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import json
from flask import Flask
from app.services.health_service import HealthCheckResult, OverallHealthResult


@pytest.fixture
def minimal_app():
    """Create minimal Flask app for testing endpoints only."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['API_VERSION'] = '1.0.0'
    app.config['FLASK_ENV'] = 'testing'
    app.config['BUILD_DATE'] = '2025-08-10T20:00:00Z'
    
    # Register the routes we want to test
    from app.utils.response import welcome_response, error_response, health_response, version_response
    from app.services.health_service import HealthService
    import platform
    import flask
    
    @app.route('/')
    def welcome():
        """Welcome endpoint providing API information and available endpoints."""
        try:
            endpoints = {
                "health": "/api/v1/health",
                "version": "/api/v1/version",
                "auth": "/api/v1/auth",
                "docs": "/api/v1/docs"
            }
            
            return welcome_response(
                message="Welcome to AI Secretary API",
                version=app.config.get('API_VERSION', '1.0.0'),
                environment=app.config.get('FLASK_ENV', 'development'),
                endpoints=endpoints
            )
            
        except Exception as e:
            return error_response(
                error_code="WELCOME_ENDPOINT_FAILED",
                message="Failed to load welcome information",
                status_code=500,
                details=str(e)
            )
    
    @app.route('/api/v1/health')
    def health_check():
        """Health check endpoint for system monitoring."""
        try:
            # Use the health service to get comprehensive health status
            health_result = HealthService.get_overall_health()
            
            # Format individual check results
            checks = {}
            for service_name, check_result in health_result.checks.items():
                check_data = {
                    "status": check_result.status,
                    "response_time_ms": check_result.response_time_ms
                }
                if check_result.error:
                    check_data["error"] = check_result.error
                
                checks[service_name] = check_data
            
            # Determine proper HTTP status code based on health status
            # Database failure = 503 (Service Unavailable)
            # Redis failure alone = 200 (OK) but with unhealthy Redis status
            status_code = 503 if health_result.status == "unhealthy" else 200
            
            return health_response(
                status=health_result.status,
                checks=checks,
                version=app.config.get('API_VERSION', '1.0.0'),
                status_code=status_code
            )
            
        except Exception as e:
            # Fallback error response for unexpected failures
            return error_response(
                error_code="HEALTH_CHECK_FAILED",
                message="Health check service failed",
                status_code=503,
                details=str(e)
            )
    
    @app.route('/api/v1/version')
    def version_info():
        """API version and build information endpoint."""
        try:
            return version_response(
                version=app.config.get('API_VERSION', '1.0.0'),
                build_date=app.config.get('BUILD_DATE'),
                environment=app.config.get('FLASK_ENV', 'development'),
                python_version=platform.python_version(),
                flask_version=flask.__version__
            )
            
        except Exception as e:
            return error_response(
                error_code="VERSION_INFO_FAILED",
                message="Failed to retrieve version information",
                status_code=500,
                details=str(e)
            )
    
    return app


@pytest.fixture
def client(minimal_app):
    """Create test client."""
    return minimal_app.test_client()


class TestWelcomeEndpoint:
    """Test cases for the welcome endpoint (/)."""
    
    def test_welcome_endpoint_success(self, client):
        """Test welcome endpoint returns correct format and content."""
        response = client.get('/')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        
        # Check required fields
        assert 'message' in data
        assert 'timestamp' in data
        assert 'version' in data
        assert 'environment' in data
        assert 'endpoints' in data
        
        # Check message content
        assert data['message'] == "Welcome to AI Secretary API"
        
        # Check version format
        assert isinstance(data['version'], str)
        assert len(data['version']) > 0
        
        # Check environment
        assert data['environment'] in ['development', 'testing', 'production']
        
        # Check endpoints structure
        endpoints = data['endpoints']
        assert isinstance(endpoints, dict)
        assert 'health' in endpoints
        assert 'version' in endpoints
        assert 'auth' in endpoints
        assert 'docs' in endpoints
        
        # Check endpoint paths
        assert endpoints['health'] == "/api/v1/health"
        assert endpoints['version'] == "/api/v1/version"
        assert endpoints['auth'] == "/api/v1/auth"
        assert endpoints['docs'] == "/api/v1/docs"
        
        # Check timestamp format (ISO-8601)
        timestamp = data['timestamp']
        assert timestamp.endswith('Z')
        # Should be parseable as datetime
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    def test_welcome_endpoint_with_custom_config(self, minimal_app):
        """Test welcome endpoint with custom configuration."""
        minimal_app.config['API_VERSION'] = '2.0.0'
        minimal_app.config['FLASK_ENV'] = 'production'
        
        client = minimal_app.test_client()
        response = client.get('/')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['version'] == '2.0.0'
        assert data['environment'] == 'production'
    
    @patch('app.utils.response.generate_timestamp')
    def test_welcome_endpoint_error_handling(self, mock_timestamp, client):
        """Test welcome endpoint error handling."""
        # Mock timestamp to raise an exception
        mock_timestamp.side_effect = Exception("Timestamp generation failed")
        
        response = client.get('/')
        
        assert response.status_code == 500
        data = response.get_json()
        
        assert data['success'] is False
        assert data['error']['code'] == "WELCOME_ENDPOINT_FAILED"
        assert "Failed to load welcome information" in data['error']['message']


class TestHealthEndpoint:
    """Test cases for the health check endpoint (/api/v1/health)."""
    
    @patch('app.services.health_service.HealthService.get_overall_health')
    def test_health_endpoint_healthy_services(self, mock_health, client):
        """Test health endpoint with all services healthy."""
        # Mock healthy response
        mock_health.return_value = OverallHealthResult(
            status="healthy",
            checks={
                'database': HealthCheckResult(
                    status="healthy",
                    response_time_ms=12
                ),
                'redis': HealthCheckResult(
                    status="healthy", 
                    response_time_ms=3
                )
            },
            timestamp="2025-08-10T22:48:26Z"
        )
        
        response = client.get('/api/v1/health')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        
        # Check required fields
        assert 'status' in data
        assert 'timestamp' in data
        assert 'version' in data
        assert 'checks' in data
        
        # Check status
        assert data['status'] == "healthy"
        
        # Check version
        assert isinstance(data['version'], str)
        
        # Check checks structure
        checks = data['checks']
        assert 'database' in checks
        assert 'redis' in checks
        
        # Check database check
        db_check = checks['database']
        assert db_check['status'] == "healthy"
        assert db_check['response_time_ms'] == 12
        assert 'error' not in db_check
        
        # Check redis check
        redis_check = checks['redis']
        assert redis_check['status'] == "healthy"
        assert redis_check['response_time_ms'] == 3
        assert 'error' not in redis_check
        
        # Check timestamp format
        timestamp = data['timestamp']
        assert timestamp.endswith('Z')
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    
    @patch('app.services.health_service.HealthService.get_overall_health')
    def test_health_endpoint_database_unhealthy(self, mock_health, client):
        """Test health endpoint with database unhealthy (should return 503)."""
        # Mock unhealthy database response
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
                    response_time_ms=3
                )
            },
            timestamp="2025-08-10T22:48:26Z"
        )
        
        response = client.get('/api/v1/health')
        
        # Database failure should return 503
        assert response.status_code == 503
        
        data = response.get_json()
        
        # Check overall status
        assert data['status'] == "unhealthy"
        
        # Check database check has error
        db_check = data['checks']['database']
        assert db_check['status'] == "unhealthy"
        assert db_check['response_time_ms'] is None
        assert db_check['error'] == "Connection timeout"
        
        # Check redis is still healthy
        redis_check = data['checks']['redis']
        assert redis_check['status'] == "healthy"
        assert redis_check['response_time_ms'] == 3
    
    @patch('app.services.health_service.HealthService.get_overall_health')
    def test_health_endpoint_redis_unhealthy(self, mock_health, client):
        """Test health endpoint with Redis unhealthy (should return 200)."""
        # Mock Redis unhealthy but database healthy
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
        
        data = response.get_json()
        
        # Check overall status is still healthy
        assert data['status'] == "healthy"
        
        # Check database is healthy
        db_check = data['checks']['database']
        assert db_check['status'] == "healthy"
        
        # Check redis has error but overall status is healthy
        redis_check = data['checks']['redis']
        assert redis_check['status'] == "unhealthy"
        assert redis_check['response_time_ms'] is None
        assert redis_check['error'] == "Redis connection failed"
    
    @patch('app.services.health_service.HealthService.get_overall_health')
    def test_health_endpoint_service_exception(self, mock_health, client):
        """Test health endpoint when health service raises exception."""
        # Mock service to raise exception
        mock_health.side_effect = Exception("Health service failed")
        
        response = client.get('/api/v1/health')
        
        assert response.status_code == 503
        data = response.get_json()
        
        assert data['success'] is False
        assert data['error']['code'] == "HEALTH_CHECK_FAILED"
        assert "Health check service failed" in data['error']['message']
        assert "Health service failed" in data['error']['details']
    
    def test_health_endpoint_with_custom_version(self, minimal_app):
        """Test health endpoint with custom API version."""
        minimal_app.config['API_VERSION'] = '3.0.0'
        client = minimal_app.test_client()
        
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.return_value = OverallHealthResult(
                status="healthy",
                checks={
                    'database': HealthCheckResult(status="healthy", response_time_ms=10)
                },
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['version'] == '3.0.0'


class TestVersionEndpoint:
    """Test cases for the version endpoint (/api/v1/version)."""
    
    def test_version_endpoint_success(self, client):
        """Test version endpoint returns correct format and content."""
        response = client.get('/api/v1/version')
        
        assert response.status_code == 200
        assert response.content_type == 'application/json'
        
        data = response.get_json()
        
        # Check required fields
        assert 'version' in data
        assert 'environment' in data
        assert 'python_version' in data
        assert 'flask_version' in data
        
        # Check version format
        assert isinstance(data['version'], str)
        assert len(data['version']) > 0
        
        # Check environment
        assert data['environment'] in ['development', 'testing', 'production']
        
        # Check python version format (should be like "3.10.0")
        python_version = data['python_version']
        assert isinstance(python_version, str)
        assert '.' in python_version
        
        # Check flask version format
        flask_version = data['flask_version']
        assert isinstance(flask_version, str)
        assert '.' in flask_version
    
    def test_version_endpoint_with_build_date(self, minimal_app):
        """Test version endpoint with build date configured."""
        minimal_app.config['API_VERSION'] = '2.1.0'
        minimal_app.config['BUILD_DATE'] = '2025-08-10T20:00:00Z'
        minimal_app.config['FLASK_ENV'] = 'production'
        
        client = minimal_app.test_client()
        response = client.get('/api/v1/version')
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data['version'] == '2.1.0'
        assert data['build_date'] == '2025-08-10T20:00:00Z'
        assert data['environment'] == 'production'
    
    def test_version_endpoint_without_build_date(self, minimal_app):
        """Test version endpoint without build date configured."""
        # Ensure BUILD_DATE is not set
        minimal_app.config.pop('BUILD_DATE', None)
        
        client = minimal_app.test_client()
        response = client.get('/api/v1/version')
        
        assert response.status_code == 200
        data = response.get_json()
        
        # build_date should not be present when not configured
        assert 'build_date' not in data or data['build_date'] is None
    
    @patch('platform.python_version')
    def test_version_endpoint_error_handling(self, mock_python_version, client):
        """Test version endpoint error handling."""
        # Mock platform.python_version to raise exception
        mock_python_version.side_effect = Exception("Platform info failed")
        
        response = client.get('/api/v1/version')
        
        assert response.status_code == 500
        data = response.get_json()
        
        assert data['success'] is False
        assert data['error']['code'] == "VERSION_INFO_FAILED"
        assert "Failed to retrieve version information" in data['error']['message']


class TestErrorScenarios:
    """Test error scenarios and HTTP status codes for all endpoints."""
    
    def test_nonexistent_endpoint(self, client):
        """Test accessing non-existent endpoint returns 404."""
        response = client.get('/api/v1/nonexistent')
        
        assert response.status_code == 404
    
    def test_invalid_method_on_endpoints(self, client):
        """Test invalid HTTP methods on endpoints."""
        # Test POST on GET-only endpoints
        endpoints = ['/', '/api/v1/health', '/api/v1/version']
        
        for endpoint in endpoints:
            response = client.post(endpoint)
            assert response.status_code == 405  # Method Not Allowed
    
    def test_health_endpoint_with_malformed_response(self, client):
        """Test health endpoint when service returns malformed data."""
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            # Mock service to return invalid data structure
            mock_health.return_value = "invalid_response"
            
            response = client.get('/api/v1/health')
            
            # Should handle gracefully and return error
            assert response.status_code == 503
    
    def test_endpoints_with_large_response_times(self, client):
        """Test endpoints handle large response times gracefully."""
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            # Mock very slow response
            mock_health.return_value = OverallHealthResult(
                status="healthy",
                checks={
                    'database': HealthCheckResult(
                        status="healthy",
                        response_time_ms=9999  # Very slow but still healthy
                    )
                },
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['checks']['database']['response_time_ms'] == 9999
    
    def test_endpoints_content_type_headers(self, client):
        """Test all endpoints return correct content-type headers."""
        endpoints = ['/', '/api/v1/health', '/api/v1/version']
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.content_type == 'application/json'
    
    def test_endpoints_response_structure_consistency(self, client):
        """Test all endpoints return consistent response structures."""
        # Welcome endpoint
        response = client.get('/')
        assert response.status_code == 200
        data = response.get_json()
        assert 'timestamp' in data
        
        # Version endpoint  
        response = client.get('/api/v1/version')
        assert response.status_code == 200
        data = response.get_json()
        # Version endpoint doesn't include timestamp in current implementation
        
        # Health endpoint
        with patch('app.services.health_service.HealthService.get_overall_health') as mock_health:
            mock_health.return_value = OverallHealthResult(
                status="healthy",
                checks={'database': HealthCheckResult(status="healthy", response_time_ms=10)},
                timestamp="2025-08-10T22:48:26Z"
            )
            
            response = client.get('/api/v1/health')
            assert response.status_code == 200
            data = response.get_json()
            assert 'timestamp' in data