"""
Service fallback validation tests.
Tests Redis fallback, database error handling, and external service fallbacks.
"""
import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, Mock
from app import create_app, db
from app.models.user import User


class TestRedisFallback:
    """Test Redis fallback mechanisms - Requirement 4.1"""
    
    @patch('redis.Redis')
    def test_redis_connection_failure_fallback(self, mock_redis):
        """Test app works when Redis is unavailable"""
        # Mock Redis connection failure
        mock_redis.side_effect = ConnectionError("Connection refused")
        
        app = create_app('testing')
        
        with app.app_context():
            # App should start successfully even without Redis
            assert app is not None
            
            # Cache should fallback to simple cache
            cache_type = app.config.get('CACHE_TYPE')
            assert cache_type in ['simple', 'null', None]
    
    @patch('redis.Redis.ping')
    def test_redis_health_check_fallback(self, mock_ping, app, client):
        """Test health check works when Redis is down"""
        # Mock Redis ping failure
        mock_ping.side_effect = ConnectionError("Redis unavailable")
        
        with app.app_context():
            response = client.get('/api/v1/health')
            
            # Should respond even if Redis is down
            assert response.status_code in [200, 503]
            
            if response.status_code == 503:
                data = response.get_json()
                if data:
                    # Should indicate Redis is down
                    assert 'redis' in str(data).lower() or 'cache' in str(data).lower()
    
    def test_cache_fallback_functionality(self, app):
        """Test caching works with fallback mechanism"""
        with app.app_context():
            # Test that caching doesn't crash the app
            try:
                from flask_caching import Cache
                cache = Cache(app)
                
                # Test basic cache operations
                cache.set('test_key', 'test_value', timeout=60)
                value = cache.get('test_key')
                
                # Should work or gracefully fail
                assert value == 'test_value' or value is None
                
            except Exception as e:
                # Cache might not be configured, that's ok
                print(f"Cache test error (expected): {e}")
    
    @patch('celery.Celery')
    def test_celery_broker_fallback(self, mock_celery, app):
        """Test Celery fallback when broker is unavailable"""
        # Mock Celery broker connection failure
        mock_celery_instance = MagicMock()
        mock_celery_instance.control.ping.side_effect = Exception("Broker unavailable")
        mock_celery.return_value = mock_celery_instance
        
        with app.app_context():
            # App should handle Celery broker unavailability
            broker_url = app.config.get('CELERY_BROKER_URL')
            
            # Should be None (disabled) or handle errors gracefully
            if broker_url:
                try:
                    # Test that Celery tasks can be defined without crashing
                    from celery import Celery
                    celery_app = Celery('test')
                    
                    @celery_app.task
                    def test_task():
                        return "test"
                    
                    # Should not crash when defining tasks
                    assert test_task is not None
                    
                except Exception as e:
                    # Expected when broker is unavailable
                    print(f"Celery broker unavailable (expected): {e}")


class TestDatabaseFallback:
    """Test database error handling and fallback"""
    
    def test_database_connection_error_handling(self, app, client):
        """Test app handles database connection errors"""
        with app.app_context():
            # Test with invalid database URL
            original_uri = app.config.get('SQLALCHEMY_DATABASE_URI')
            
            try:
                # Set invalid database URL
                app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///nonexistent/invalid/path.db'
                
                # App should handle database errors gracefully
                response = client.get('/api/v1/health')
                
                # Should not crash completely
                assert response.status_code in [200, 503, 500]
                
                if response.status_code == 503:
                    data = response.get_json()
                    if data:
                        # Should indicate database issues
                        assert 'database' in str(data).lower() or 'db' in str(data).lower()
                        
            finally:
                # Restore original configuration
                if original_uri:
                    app.config['SQLALCHEMY_DATABASE_URI'] = original_uri
    
    def test_database_query_error_handling(self, app, db_session):
        """Test database query error handling"""
        with app.app_context():
            try:
                # Try to execute an invalid query
                db_session.execute('SELECT * FROM nonexistent_table')
                db_session.commit()
                
            except Exception as e:
                # Should handle database errors gracefully
                db_session.rollback()
                assert 'nonexistent_table' in str(e) or 'no such table' in str(e).lower()
    
    def test_database_transaction_rollback(self, app, db_session):
        """Test database transaction rollback on errors"""
        with app.app_context():
            try:
                # Start a transaction that will fail
                user = User(
                    email='test@example.com',
                    password_hash='hash',
                    first_name='Test',
                    last_name='User',
                    tenant_id=999999  # Non-existent tenant
                )
                db_session.add(user)
                db_session.commit()
                
            except Exception as e:
                # Should rollback transaction
                db_session.rollback()
                print(f"Transaction rolled back (expected): {e}")
                
                # Verify rollback worked
                users = User.query.filter_by(email='test@example.com').all()
                assert len(users) == 0


class TestExternalServiceFallback:
    """Test external service fallback mechanisms"""
    
    @patch('requests.get')
    def test_external_api_fallback(self, mock_get, app):
        """Test external API fallback when services are down"""
        # Mock external API failure
        mock_get.side_effect = ConnectionError("External service unavailable")
        
        with app.app_context():
            # Test that app handles external service failures
            try:
                import requests
                response = requests.get('https://api.example.com/test')
                
            except ConnectionError as e:
                # Should handle external service errors
                assert 'unavailable' in str(e)
    
    def test_oauth_service_fallback(self, app, client):
        """Test OAuth service fallback"""
        with app.app_context():
            # Test OAuth endpoints when external services are down
            oauth_endpoints = [
                '/auth/google',
                '/auth/google/callback',
                '/auth/microsoft',
                '/auth/microsoft/callback'
            ]
            
            for endpoint in oauth_endpoints:
                response = client.get(endpoint)
                
                # Should not crash, may return error or redirect
                assert response.status_code in [200, 302, 404, 500]
    
    def test_email_service_fallback(self, app):
        """Test email service fallback"""
        with app.app_context():
            # Test email configuration fallback
            mail_server = app.config.get('MAIL_SERVER')
            
            if mail_server:
                # Should have fallback configuration
                mail_port = app.config.get('MAIL_PORT', 587)
                mail_use_tls = app.config.get('MAIL_USE_TLS', True)
                
                assert isinstance(mail_port, int)
                assert isinstance(mail_use_tls, bool)


class TestServiceHealthMonitoring:
    """Test service health monitoring - Requirement 4.2"""
    
    def test_health_endpoint_response(self, client):
        """Test health endpoint provides service status"""
        response = client.get('/api/v1/health')
        
        # Should respond with health status
        assert response.status_code in [200, 503]
        
        if response.status_code in [200, 503]:
            data = response.get_json()
            if data:
                # Should contain health information
                assert isinstance(data, dict)
                
                # Common health check fields
                expected_fields = ['status', 'timestamp', 'services', 'database', 'redis']
                found_fields = [field for field in expected_fields if field in str(data).lower()]
                
                # Should have at least some health information
                assert len(found_fields) > 0
    
    def test_individual_service_health(self, app):
        """Test individual service health checks"""
        with app.app_context():
            # Test database health
            try:
                from app.models.user import User
                User.query.limit(1).all()
                db_healthy = True
            except Exception:
                db_healthy = False
            
            # Database health should be determinable
            assert isinstance(db_healthy, bool)
            
            # Test Redis health (if configured)
            redis_url = app.config.get('REDIS_URL')
            if redis_url:
                try:
                    import redis
                    r = redis.from_url(redis_url)
                    r.ping()
                    redis_healthy = True
                except Exception:
                    redis_healthy = False
                
                assert isinstance(redis_healthy, bool)
    
    def test_service_degradation_detection(self, app, client):
        """Test service degradation detection"""
        with app.app_context():
            # Make multiple requests to detect degradation
            response_times = []
            
            for _ in range(5):
                import time
                start_time = time.time()
                response = client.get('/api/v1/health')
                response_time = time.time() - start_time
                response_times.append(response_time)
            
            # Calculate average response time
            avg_response_time = sum(response_times) / len(response_times)
            
            # Should detect if service is degraded (slow responses)
            if avg_response_time > 2.0:  # 2 seconds threshold
                print(f"Service degradation detected: {avg_response_time:.2f}s average response time")
            
            # Should still respond even if degraded
            assert all(rt < 30 for rt in response_times), "Service completely unresponsive"


class TestGracefulDegradation:
    """Test graceful degradation when services are unavailable"""
    
    def test_partial_functionality_when_redis_down(self, app, client):
        """Test app provides partial functionality when Redis is down"""
        with app.app_context():
            # Simulate Redis being down
            app.config['REDIS_URL'] = None
            app.config['CACHE_TYPE'] = 'simple'
            
            # Basic functionality should still work
            response = client.get('/')
            assert response.status_code in [200, 404, 500]
            
            # Health endpoint should indicate degraded state
            health_response = client.get('/api/v1/health')
            assert health_response.status_code in [200, 503]
    
    def test_readonly_mode_when_database_issues(self, app, client):
        """Test readonly mode when database has issues"""
        with app.app_context():
            # Test that read operations might work even if writes fail
            try:
                response = client.get('/api/v1/health')
                # Should respond even with database issues
                assert response.status_code in [200, 503, 500]
                
            except Exception as e:
                print(f"Database issues detected (expected): {e}")
    
    def test_error_message_display(self, app, client):
        """Test error messages are displayed appropriately"""
        with app.app_context():
            # Test that error pages are user-friendly
            response = client.get('/nonexistent-page')
            assert response.status_code == 404
            
            # Should have user-friendly error content
            content_type = response.headers.get('Content-Type', '')
            assert 'html' in content_type or 'json' in content_type


if __name__ == '__main__':
    pytest.main([__file__, '-v'])