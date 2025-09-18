"""
Comprehensive Authentication Integration Tests

This module provides comprehensive integration tests for authentication
flow with both PostgreSQL and SQLite databases, covering all authentication
scenarios and database switching.

Requirements covered: 2.1, 2.2, 2.3, 4.1, 4.2, 4.3
"""
import os
import pytest
import tempfile
import time
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import psycopg2
import sqlite3
from flask_jwt_extended import create_access_token, decode_token

from app.utils.adaptive_config import get_adaptive_config
from app.utils.database_manager import DatabaseManager


class TestAuthenticationWithSQLite:
    """Test authentication flow with SQLite database."""
    
    @pytest.fixture
    def sqlite_app(self):
        """Create app configured for SQLite."""
        from app import create_app
        
        # Create temporary database
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        
        # Mock PostgreSQL as unavailable to force SQLite
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 1  # Connection failed
                mock_socket.return_value = mock_sock
                
                app = create_app('testing')
                app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
                app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}
                app.config['DB_SCHEMA'] = None
                app.config['TESTING'] = True
                app.config['WTF_CSRF_ENABLED'] = False
                
                with app.app_context():
                    from app import db
                    db.create_all()
                    
                    # Create admin user for testing
                    from app.models.tenant import Tenant
                    from app.models.user import User
                    
                    tenant = Tenant(
                        name="Test Tenant",
                        domain="test.example.com",
                        slug="test-tenant"
                    )
                    db.session.add(tenant)
                    db.session.commit()
                    
                    admin_user = User(
                        tenant_id=tenant.id,
                        email="admin@ai-secretary.com",
                        first_name="Admin",
                        last_name="User",
                        role="admin",
                        is_active=True
                    )
                    admin_user.set_password("admin123")
                    db.session.add(admin_user)
                    db.session.commit()
                    
                    yield app
        
        os.close(db_fd)
        os.unlink(db_path)
    
    def test_admin_login_with_sqlite(self, sqlite_app):
        """Test admin login with SQLite database."""
        with sqlite_app.test_client() as client:
            # Test login with correct credentials
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            response = client.post('/api/v1/auth/login', json=login_data)
            
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
            assert 'access_token' in data['data']
            assert 'refresh_token' in data['data']
            
            # Verify token contains correct claims
            token = data['data']['access_token']
            decoded = decode_token(token)
            assert 'tenant_id' in decoded
            assert 'user_id' in decoded
            assert 'role' in decoded
            assert decoded['role'] == 'admin'
    
    def test_protected_endpoint_access_with_sqlite(self, sqlite_app):
        """Test protected endpoint access with SQLite authentication."""
        with sqlite_app.test_client() as client:
            with sqlite_app.app_context():
                # Create access token
                from app.models.user import User
                user = User.query.filter_by(email='admin@ai-secretary.com').first()
                
                token = create_access_token(
                    identity=user.id,
                    additional_claims={
                        'tenant_id': user.tenant_id,
                        'user_id': user.id,
                        'role': user.role
                    }
                )
                
                headers = {
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json'
                }
                
                # Test protected endpoint
                response = client.get('/api/v1/auth/me', headers=headers)
                
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert data['data']['email'] == 'admin@ai-secretary.com'
                assert data['data']['role'] == 'admin'
    
    def test_token_refresh_with_sqlite(self, sqlite_app):
        """Test token refresh with SQLite database."""
        with sqlite_app.test_client() as client:
            # First login to get refresh token
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            login_response = client.post('/api/v1/auth/login', json=login_data)
            login_data = login_response.get_json()
            refresh_token = login_data['data']['refresh_token']
            
            # Use refresh token to get new access token
            headers = {
                'Authorization': f'Bearer {refresh_token}',
                'Content-Type': 'application/json'
            }
            
            refresh_response = client.post('/api/v1/auth/refresh', headers=headers)
            
            assert refresh_response.status_code == 200
            refresh_data = refresh_response.get_json()
            assert refresh_data['success'] is True
            assert 'access_token' in refresh_data['data']
    
    def test_logout_with_sqlite(self, sqlite_app):
        """Test logout functionality with SQLite database."""
        with sqlite_app.test_client() as client:
            # Login first
            login_data = {
                'email': 'admin@ai-secretary.com',
                'password': 'admin123'
            }
            
            login_response = client.post('/api/v1/auth/login', json=login_data)
            login_data = login_response.get_json()
            access_token = login_data['data']['access_token']
            
            # Logout
            headers = {
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            }
            
            logout_response = client.post('/api/v1/auth/logout', headers=headers)
            
            assert logout_response.status_code == 200
            logout_data = logout_response.get_json()
            assert logout_data['success'] is True
            assert 'Logged out successfully' in logout_data['message']


class TestAuthenticationWithPostgreSQL:
    """Test authentication flow with PostgreSQL database."""
    
    @pytest.fixture
    def postgresql_app(self):
        """Create app configured for PostgreSQL (mocked)."""
        from app import create_app
        
        # Mock PostgreSQL as available
        with patch('psycopg2.connect') as mock_connect:
            mock_conn = MagicMock()
            mock_connect.return_value = mock_conn
            
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                mock_sock.connect_ex.return_value = 0  # Success
                mock_socket.return_value = mock_sock
                
                app = create_app('testing')
                app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://test:test@localhost/test'
                app.config['DB_SCHEMA'] = 'ai_secretary'
                app.config['TESTING'] = True
                app.config['WTF_CSRF_ENABLED'] = False
                
                # Mock database operations for PostgreSQL
                with patch('app.db.create_all'):
                    with app.app_context():
                        yield app
    
    def test_postgresql_configuration_detection(self, postgresql_app):
        """Test that PostgreSQL configuration is properly detected."""
        with postgresql_app.app_context():
            # Check that the app is configured for PostgreSQL
            assert 'postgresql://' in postgresql_app.config['SQLALCHEMY_DATABASE_URI']
            assert postgresql_app.config.get('DB_SCHEMA') == 'ai_secretary'
    
    def test_authentication_endpoints_with_postgresql(self, postgresql_app):
        """Test authentication endpoints with PostgreSQL configuration."""
        with postgresql_app.test_client() as client:
            # Mock user authentication for PostgreSQL
            with patch('app.models.user.User.authenticate') as mock_auth:
                mock_user = MagicMock()
                mock_user.id = 1
                mock_user.tenant_id = 1
                mock_user.email = 'admin@ai-secretary.com'
                mock_user.role = 'admin'
                mock_auth.return_value = mock_user
                
                login_data = {
                    'email': 'admin@ai-secretary.com',
                    'password': 'admin123'
                }
                
                response = client.post('/api/v1/auth/login', json=login_data)
                
                # Should work the same as SQLite
                assert response.status_code == 200
                data = response.get_json()
                assert data['success'] is True
                assert 'access_token' in data['data']


class TestDatabaseSwitchingScenarios:
    """Test authentication during database switching scenarios."""
    
    def test_postgresql_to_sqlite_fallback_during_auth(self):
        """Test authentication when PostgreSQL fails and falls back to SQLite."""
        from app import create_app
        
        # Create temporary SQLite database
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        
        try:
            # Initially try PostgreSQL, then fallback to SQLite
            with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("PostgreSQL down")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1  # PostgreSQL connection failed
                    mock_socket.return_value = mock_sock
                    
                    app = create_app('testing')
                    app.config['SQLITE_DATABASE_URL'] = f'sqlite:///{db_path}'
                    app.config['TESTING'] = True
                    
                    with app.app_context():
                        # Verify SQLite fallback occurred
                        assert app.config.get('DETECTED_DATABASE_TYPE') == 'sqlite'
                        assert app.config.get('DB_SCHEMA') is None
                        
                        # Authentication should still work
                        from app import db
                        db.create_all()
                        
                        # Create test user
                        from app.models.tenant import Tenant
                        from app.models.user import User
                        
                        tenant = Tenant(name="Test", slug="test")
                        db.session.add(tenant)
                        db.session.commit()
                        
                        user = User(
                            tenant_id=tenant.id,
                            email="test@example.com",
                            role="admin",
                            is_active=True
                        )
                        user.set_password("password123")
                        db.session.add(user)
                        db.session.commit()
                        
                        # Test authentication works with SQLite fallback
                        authenticated_user = User.authenticate("test@example.com", "password123", tenant.id)
                        assert authenticated_user is not None
                        assert authenticated_user.email == "test@example.com"
        
        finally:
            os.close(db_fd)
            os.unlink(db_path)
    
    def test_service_degradation_during_authentication(self):
        """Test authentication when external services are degraded."""
        from app import create_app
        
        # Mock all external services as unavailable
        with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
            with patch('redis.from_url', side_effect=Exception("No Redis")):
                with patch('socket.socket') as mock_socket:
                    mock_sock = MagicMock()
                    mock_sock.connect_ex.return_value = 1  # All connections fail
                    mock_socket.return_value = mock_sock
                    
                    app = create_app('testing')
                    app.config['TESTING'] = True
                    
                    with app.app_context():
                        # App should still start with degraded services
                        assert app.config.get('DETECTED_DATABASE_TYPE') == 'sqlite'
                        assert app.config.get('CACHE_TYPE') == 'simple'
                        
                        # Feature flags should reflect degraded state
                        features = app.config.get('FEATURES', {})
                        assert features.get('database_postgresql') is False
                        assert features.get('cache_redis') is False
                        assert features.get('celery') is False
                        assert features.get('cache_simple') is True
                        assert features.get('websockets') is True
    
    def test_authentication_consistency_across_databases(self):
        """Test that authentication behavior is consistent across database types."""
        test_scenarios = [
            {
                'name': 'SQLite',
                'mock_postgresql': True,  # Mock PostgreSQL as unavailable
                'expected_db_type': 'sqlite'
            },
            {
                'name': 'PostgreSQL',
                'mock_postgresql': False,  # Mock PostgreSQL as available
                'expected_db_type': 'postgresql'
            }
        ]
        
        for scenario in test_scenarios:
            with patch('socket.socket') as mock_socket:
                mock_sock = MagicMock()
                if scenario['mock_postgresql']:
                    mock_sock.connect_ex.return_value = 1  # Fail PostgreSQL
                else:
                    mock_sock.connect_ex.return_value = 0  # Success PostgreSQL
                mock_socket.return_value = mock_sock
                
                if scenario['mock_postgresql']:
                    with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                        config_class = get_adaptive_config('testing')
                else:
                    with patch('psycopg2.connect') as mock_connect:
                        mock_connect.return_value = MagicMock()
                        config_class = get_adaptive_config('testing')
                
                config = config_class()
                
                # Verify expected database type
                assert config.DETECTED_DATABASE_TYPE == scenario['expected_db_type']
                
                # JWT configuration should be consistent
                assert hasattr(config, 'JWT_SECRET_KEY')
                assert hasattr(config, 'JWT_ACCESS_TOKEN_EXPIRES')
                
                # Authentication endpoints should be available regardless of database
                # (This would be tested in actual endpoint tests)


class TestAuthenticationErrorHandling:
    """Test authentication error handling in different database scenarios."""
    
    def test_database_connection_loss_during_auth(self):
        """Test authentication when database connection is lost."""
        from app import create_app
        
        app = create_app('testing')
        
        with app.app_context():
            # Mock database connection loss
            with patch('app.models.user.User.authenticate', side_effect=Exception("Database connection lost")):
                with app.test_client() as client:
                    login_data = {
                        'email': 'admin@ai-secretary.com',
                        'password': 'admin123'
                    }
                    
                    response = client.post('/api/v1/auth/login', json=login_data)
                    
                    # Should handle database errors gracefully
                    assert response.status_code in [500, 503]  # Server error or service unavailable
                    data = response.get_json()
                    assert data['success'] is False
    
    def test_token_validation_with_database_issues(self):
        """Test token validation when database has issues."""
        from app import create_app
        
        app = create_app('testing')
        
        with app.app_context():
            # Create a valid token
            token = create_access_token(
                identity=1,
                additional_claims={
                    'tenant_id': 1,
                    'user_id': 1,
                    'role': 'admin'
                }
            )
            
            headers = {
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json'
            }
            
            # Mock database issues during token validation
            with patch('app.models.user.User.query') as mock_query:
                mock_query.get.side_effect = Exception("Database error")
                
                with app.test_client() as client:
                    response = client.get('/api/v1/auth/me', headers=headers)
                    
                    # Should handle database errors during token validation
                    assert response.status_code in [401, 500]
    
    def test_authentication_with_corrupted_database(self):
        """Test authentication behavior with corrupted database."""
        # Create temporary corrupted database file
        db_fd, db_path = tempfile.mkstemp(suffix='.db')
        
        try:
            # Write invalid data to simulate corruption
            with open(db_path, 'wb') as f:
                f.write(b'corrupted database content')
            
            with patch.dict(os.environ, {'SQLITE_DATABASE_URL': f'sqlite:///{db_path}'}):
                with patch('psycopg2.connect', side_effect=psycopg2.OperationalError("No PostgreSQL")):
                    from app import create_app
                    
                    # App creation might fail with corrupted database
                    try:
                        app = create_app('testing')
                        with app.app_context():
                            from app import db
                            # This should fail with corrupted database
                            db.create_all()
                    except Exception as e:
                        # Should handle corrupted database gracefully
                        assert "database" in str(e).lower() or "disk" in str(e).lower()
        
        finally:
            os.close(db_fd)
            os.unlink(db_path)