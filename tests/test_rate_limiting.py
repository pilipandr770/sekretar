"""Tests for rate limiting functionality."""
import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from flask import Flask, g, request
import redis

from app.utils.rate_limiter import (
    RateLimitConfig, RateLimitManager, create_limiter, 
    get_rate_limit_key, get_tenant_rate_limit_key, get_user_rate_limit_key
)
from app.utils.rate_limit_decorators import (
    rate_limit, auth_rate_limit, api_rate_limit, admin_rate_limit,
    _rate_limit_exceeded_response, RateLimitMiddleware
)


class TestRateLimitConfig:
    """Test rate limit configuration."""
    
    def test_default_limits(self):
        """Test default rate limits."""
        assert RateLimitConfig.DEFAULT_LIMITS == ["1000 per hour", "100 per minute"]
    
    def test_auth_limits(self):
        """Test authentication endpoint limits."""
        assert RateLimitConfig.AUTH_LIMITS == ["10 per minute", "50 per hour"]
    
    def test_get_limits_for_endpoint(self):
        """Test getting limits for specific endpoints."""
        # Auth endpoint
        auth_limits = RateLimitConfig.get_limits_for_endpoint("/api/v1/auth/login")
        assert auth_limits == RateLimitConfig.AUTH_LIMITS
        
        # CRM endpoint
        crm_limits = RateLimitConfig.get_limits_for_endpoint("/api/v1/crm/leads")
        assert crm_limits == RateLimitConfig.API_LIMITS["crm"]
        
        # Unknown endpoint
        default_limits = RateLimitConfig.get_limits_for_endpoint("/api/v1/unknown")
        assert default_limits == RateLimitConfig.DEFAULT_LIMITS
    
    def test_get_tenant_limits(self):
        """Test getting tenant-specific limits."""
        # Free plan
        free_limits = RateLimitConfig.get_tenant_limits("free")
        assert free_limits == ["100 per hour", "10 per minute"]
        
        # Pro plan
        pro_limits = RateLimitConfig.get_tenant_limits("pro")
        assert pro_limits == ["2000 per hour", "200 per minute"]
        
        # Unknown plan defaults to free
        unknown_limits = RateLimitConfig.get_tenant_limits("unknown")
        assert unknown_limits == RateLimitConfig.TENANT_LIMITS["free"]


class TestRateLimitKeyGeneration:
    """Test rate limit key generation functions."""
    
    def test_get_rate_limit_key_with_user(self, app):
        """Test rate limit key generation with user context."""
        with app.test_request_context():
            g.user_id = 123
            g.tenant_id = 456
            
            key = get_rate_limit_key()
            assert key == "user:123"
    
    def test_get_rate_limit_key_with_tenant_only(self, app):
        """Test rate limit key generation with tenant context only."""
        with app.test_request_context():
            g.tenant_id = 456
            
            key = get_rate_limit_key()
            assert key == "tenant:456"
    
    @patch('app.utils.rate_limiter.get_remote_address')
    def test_get_rate_limit_key_with_ip_fallback(self, mock_get_remote_address, app):
        """Test rate limit key generation with IP fallback."""
        mock_get_remote_address.return_value = "192.168.1.1"
        
        with app.test_request_context():
            key = get_rate_limit_key()
            assert key == "ip:192.168.1.1"
    
    def test_get_tenant_rate_limit_key(self, app):
        """Test tenant-specific rate limit key generation."""
        with app.test_request_context():
            g.tenant_id = 456
            
            key = get_tenant_rate_limit_key()
            assert key == "tenant:456"
    
    def test_get_user_rate_limit_key(self, app):
        """Test user-specific rate limit key generation."""
        with app.test_request_context():
            g.user_id = 123
            
            key = get_user_rate_limit_key()
            assert key == "user:123"


class TestRateLimitManager:
    """Test rate limit manager functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis client."""
        return Mock(spec=redis.Redis)
    
    @pytest.fixture
    def rate_limit_manager(self, mock_redis):
        """Rate limit manager with mocked Redis."""
        return RateLimitManager(mock_redis)
    
    def test_check_rate_limit_allowed(self, rate_limit_manager, mock_redis, app):
        """Test rate limit check when limit is not exceeded."""
        with app.test_request_context():
            # Mock Redis pipeline
            mock_pipeline = Mock()
            mock_pipeline.execute.return_value = [None, 5, None, None]  # 5 current requests
            mock_redis.pipeline.return_value = mock_pipeline
            
            result = rate_limit_manager.check_rate_limit("test_key", 10, 60)
            
            assert result['allowed'] is True
            assert result['limit'] == 10
            assert result['remaining'] == 4  # 10 - 5 - 1
            assert result['current_count'] == 5
    
    def test_check_rate_limit_exceeded(self, rate_limit_manager, mock_redis, app):
        """Test rate limit check when limit is exceeded."""
        with app.test_request_context():
            # Mock Redis pipeline
            mock_pipeline = Mock()
            mock_pipeline.execute.return_value = [None, 10, None, None]  # 10 current requests (at limit)
            mock_redis.pipeline.return_value = mock_pipeline
            
            result = rate_limit_manager.check_rate_limit("test_key", 10, 60)
            
            assert result['allowed'] is False
            assert result['limit'] == 10
            assert result['remaining'] == 0
            assert result['current_count'] == 10
    
    def test_check_rate_limit_redis_error(self, rate_limit_manager, mock_redis, app):
        """Test rate limit check when Redis fails."""
        with app.test_request_context():
            mock_redis.pipeline.side_effect = redis.ConnectionError("Redis connection failed")
            
            result = rate_limit_manager.check_rate_limit("test_key", 10, 60)
            
            # Should fail open (allow request)
            assert result['allowed'] is True
            assert 'error' in result
    
    @patch('app.utils.rate_limiter.Tenant')
    @patch('app.utils.rate_limiter.Subscription')
    def test_get_tenant_plan(self, mock_subscription, mock_tenant, rate_limit_manager):
        """Test getting tenant plan for rate limiting."""
        # Mock tenant and subscription
        mock_tenant_obj = Mock()
        mock_tenant.query.get.return_value = mock_tenant_obj
        
        mock_subscription_obj = Mock()
        mock_subscription_obj.plan.name = "Pro"
        mock_subscription.query.filter_by.return_value.first.return_value = mock_subscription_obj
        
        plan = rate_limit_manager.get_tenant_plan(123)
        assert plan == "pro"
    
    @patch('app.utils.rate_limiter.Tenant')
    def test_get_tenant_plan_no_subscription(self, mock_tenant, rate_limit_manager):
        """Test getting tenant plan when no subscription exists."""
        mock_tenant_obj = Mock()
        mock_tenant.query.get.return_value = mock_tenant_obj
        
        # No subscription found
        from app.models.billing import Subscription
        with patch.object(Subscription.query, 'filter_by') as mock_filter:
            mock_filter.return_value.first.return_value = None
            
            plan = rate_limit_manager.get_tenant_plan(123)
            assert plan == "free"
    
    def test_check_tenant_rate_limit(self, rate_limit_manager, mock_redis, app):
        """Test tenant-specific rate limit checking."""
        with app.test_request_context():
            with patch.object(rate_limit_manager, 'get_tenant_plan', return_value='pro'):
                with patch.object(rate_limit_manager, 'check_rate_limit') as mock_check:
                    mock_check.return_value = {'allowed': True, 'limit': 2000}
                    
                    result = rate_limit_manager.check_tenant_rate_limit(123, "/api/v1/crm/leads")
                    
                    assert result['allowed'] is True
                    mock_check.assert_called_once()
    
    def test_check_user_rate_limit(self, rate_limit_manager, mock_redis, app):
        """Test user-specific rate limit checking."""
        with app.test_request_context():
            with patch.object(rate_limit_manager, 'check_rate_limit') as mock_check:
                mock_check.return_value = {'allowed': True, 'limit': 1000}
                
                result = rate_limit_manager.check_user_rate_limit(456, "/api/v1/crm/leads")
                
                assert result['allowed'] is True
                mock_check.assert_called_once()


class TestRateLimitDecorators:
    """Test rate limiting decorators."""
    
    @pytest.fixture
    def mock_rate_limit_manager(self):
        """Mock rate limit manager."""
        manager = Mock()
        manager.check_tenant_rate_limit.return_value = {'allowed': True, 'limit': 100}
        manager.check_user_rate_limit.return_value = {'allowed': True, 'limit': 100}
        return manager
    
    def test_rate_limit_decorator_allowed(self, app, mock_rate_limit_manager):
        """Test rate limit decorator when request is allowed."""
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        @rate_limit(limits=["10 per minute"])
        def test_endpoint():
            return "success"
        
        with app.test_request_context():
            g.tenant_id = 123
            g.user_id = 456
            
            result = test_endpoint()
            assert result == "success"
    
    def test_rate_limit_decorator_tenant_exceeded(self, app, mock_rate_limit_manager):
        """Test rate limit decorator when tenant limit is exceeded."""
        mock_rate_limit_manager.check_tenant_rate_limit.return_value = {
            'allowed': False, 'limit': 100, 'remaining': 0, 'reset_time': 1234567890
        }
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        @rate_limit(limits=["10 per minute"])
        def test_endpoint():
            return "success"
        
        with app.test_request_context():
            g.tenant_id = 123
            g.user_id = 456
            
            response = test_endpoint()
            assert response.status_code == 429
            assert 'X-RateLimit-Limit' in response.headers
    
    def test_rate_limit_decorator_user_exceeded(self, app, mock_rate_limit_manager):
        """Test rate limit decorator when user limit is exceeded."""
        mock_rate_limit_manager.check_user_rate_limit.return_value = {
            'allowed': False, 'limit': 100, 'remaining': 0, 'reset_time': 1234567890
        }
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        @rate_limit(limits=["10 per minute"])
        def test_endpoint():
            return "success"
        
        with app.test_request_context():
            g.tenant_id = 123
            g.user_id = 456
            
            response = test_endpoint()
            assert response.status_code == 429
    
    def test_rate_limit_decorator_testing_mode(self, app):
        """Test rate limit decorator skips in testing mode."""
        app.config['TESTING'] = True
        
        @rate_limit(limits=["1 per minute"])
        def test_endpoint():
            return "success"
        
        with app.test_request_context():
            result = test_endpoint()
            assert result == "success"
    
    def test_auth_rate_limit_decorator(self, app, mock_rate_limit_manager):
        """Test auth-specific rate limit decorator."""
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        @auth_rate_limit()
        def login_endpoint():
            return "logged in"
        
        with app.test_request_context():
            result = login_endpoint()
            assert result == "logged in"
    
    def test_api_rate_limit_decorator(self, app, mock_rate_limit_manager):
        """Test API-specific rate limit decorator."""
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        @api_rate_limit(category="crm")
        def crm_endpoint():
            return "crm data"
        
        with app.test_request_context():
            g.tenant_id = 123
            g.user_id = 456
            
            result = crm_endpoint()
            assert result == "crm data"
    
    def test_admin_rate_limit_decorator(self, app, mock_rate_limit_manager):
        """Test admin-specific rate limit decorator."""
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        @admin_rate_limit()
        def admin_endpoint():
            return "admin data"
        
        with app.test_request_context():
            g.tenant_id = 123
            g.user_id = 456
            
            result = admin_endpoint()
            assert result == "admin data"


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""
    
    def test_middleware_initialization(self, app):
        """Test middleware initialization."""
        middleware = RateLimitMiddleware(app)
        assert middleware.app == app
    
    @patch('app.utils.rate_limit_decorators.get_remote_address')
    def test_middleware_before_request_ip_limit(self, mock_get_remote_address, app):
        """Test middleware applies IP-based rate limiting."""
        mock_get_remote_address.return_value = "192.168.1.1"
        
        mock_rate_limit_manager = Mock()
        mock_rate_limit_manager.check_rate_limit.return_value = {'allowed': True}
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        middleware = RateLimitMiddleware()
        
        with app.test_request_context('/api/v1/test'):
            result = middleware.before_request()
            assert result is None  # No rate limit exceeded
    
    @patch('app.utils.rate_limit_decorators.get_remote_address')
    def test_middleware_before_request_ip_limit_exceeded(self, mock_get_remote_address, app):
        """Test middleware handles IP rate limit exceeded."""
        mock_get_remote_address.return_value = "192.168.1.1"
        
        mock_rate_limit_manager = Mock()
        mock_rate_limit_manager.check_rate_limit.return_value = {
            'allowed': False, 'limit': 100, 'remaining': 0, 'reset_time': 1234567890
        }
        app.extensions = {'rate_limit_manager': mock_rate_limit_manager}
        
        middleware = RateLimitMiddleware()
        
        with app.test_request_context('/api/v1/test'):
            response = middleware.before_request()
            assert response.status_code == 429
    
    def test_middleware_skips_non_api_endpoints(self, app):
        """Test middleware skips non-API endpoints."""
        middleware = RateLimitMiddleware()
        
        with app.test_request_context('/static/css/style.css'):
            result = middleware.before_request()
            assert result is None
    
    def test_middleware_skips_health_checks(self, app):
        """Test middleware skips health check endpoints."""
        middleware = RateLimitMiddleware()
        
        with app.test_request_context('/api/v1/health'):
            request.endpoint = 'api.health'
            result = middleware.before_request()
            assert result is None
    
    def test_middleware_skips_testing_mode(self, app):
        """Test middleware skips in testing mode."""
        app.config['TESTING'] = True
        middleware = RateLimitMiddleware()
        
        with app.test_request_context('/api/v1/test'):
            result = middleware.before_request()
            assert result is None


class TestRateLimitResponse:
    """Test rate limit response generation."""
    
    def test_rate_limit_exceeded_response(self, app):
        """Test rate limit exceeded response format."""
        rate_limit_result = {
            'limit': 100,
            'remaining': 0,
            'reset_time': 1234567890
        }
        
        with app.test_request_context():
            response = _rate_limit_exceeded_response(rate_limit_result, 'user')
            
            assert response.status_code == 429
            assert 'X-RateLimit-Limit' in response.headers
            assert 'X-RateLimit-Remaining' in response.headers
            assert 'X-RateLimit-Reset' in response.headers
            assert 'Retry-After' in response.headers
            
            data = response.get_json()
            assert data['error']['code'] == 'RATE_LIMIT_EXCEEDED'
            assert data['error']['details']['limit_type'] == 'user'


class TestCreateLimiter:
    """Test limiter creation and configuration."""
    
    def test_create_limiter(self, app):
        """Test creating Flask-Limiter instance."""
        limiter = create_limiter(app)
        
        assert limiter is not None
        assert limiter.app == app
    
    def test_create_limiter_with_custom_redis_url(self, app):
        """Test creating limiter with custom Redis URL."""
        app.config['RATE_LIMIT_STORAGE_URL'] = 'redis://localhost:6379/5'
        
        limiter = create_limiter(app)
        assert limiter is not None


@pytest.fixture
def app():
    """Create test Flask application."""
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['REDIS_URL'] = 'redis://localhost:6379/0'
    app.config['RATE_LIMIT_STORAGE_URL'] = 'redis://localhost:6379/3'
    
    # Mock Flask-Babel for testing
    with patch('flask_babel.gettext', side_effect=lambda x, **kwargs: x):
        yield app