"""Test configuration and fixtures."""
import pytest
import tempfile
import os

# Set environment variables before importing models
os.environ['TESTING'] = 'True'
os.environ['DB_SCHEMA'] = ''

from app import create_app, db as database
from app.models.tenant import Tenant
from app.models.user import User
from app.models.kyb_monitoring import Counterparty


@pytest.fixture
def app():
    """Create application for testing."""
    # Create temporary database
    db_fd, db_path = tempfile.mkstemp()
    
    flask_app = create_app('testing')
    # Override database configuration for testing
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
    flask_app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {}  # Remove PostgreSQL-specific options
    flask_app.config['DB_SCHEMA'] = None  # Remove schema for SQLite testing
    flask_app.config['TESTING'] = True
    flask_app.config['WTF_CSRF_ENABLED'] = False
    # Disable health checks for testing to avoid external dependencies
    flask_app.config['HEALTH_CHECK_DATABASE_ENABLED'] = False
    flask_app.config['HEALTH_CHECK_REDIS_ENABLED'] = False
    flask_app.config['TENANT_MIDDLEWARE_ENABLED'] = False  # Disable tenant middleware for tests
    flask_app.config['JWT_ACCESS_TOKEN_EXPIRES'] = False  # Disable token expiration for tests
    
    with flask_app.app_context():
        # Create all tables for tests that need database
        try:
            # Import all models to ensure they're registered
            import app.models
            database.create_all()
        except Exception as e:
            # Some tests don't need database, so ignore errors
            print(f"Database creation error: {e}")
            pass
        yield flask_app
    
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def db_session(app):
    """Create database session for testing."""
    with app.app_context():
        yield database.session


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create test CLI runner."""
    return app.test_cli_runner()


@pytest.fixture
def tenant(app):
    """Create a test tenant."""
    with app.app_context():
        tenant = Tenant(
            name="Test Tenant",
            domain="test.example.com",
            slug="test-tenant",
            settings={"test": True}
        )
        database.session.add(tenant)
        database.session.commit()
        return tenant


@pytest.fixture
def user(app, tenant):
    """Create a test user."""
    with app.app_context():
        # Refresh tenant to ensure it's attached to the session
        database.session.add(tenant)
        user = User(
            tenant_id=tenant.id,
            email="test@example.com",
            password_hash="hashed_password",
            first_name="Test",
            last_name="User",
            is_active=True
        )
        database.session.add(user)
        database.session.commit()
        return user


@pytest.fixture
def counterparty(app, tenant):
    """Create a test counterparty."""
    with app.app_context():
        counterparty = Counterparty(
            tenant_id=tenant.id,
            name="Test Counterparty Ltd",
            vat_number="GB123456789",
            country_code="GB"
        )
        database.session.add(counterparty)
        database.session.commit()
        return counterparty


@pytest.fixture
def auth_headers(app, user):
    """Create authentication headers for testing."""
    from flask_jwt_extended import create_access_token
    
    with app.app_context():
        # Refresh user to ensure it's attached to the session
        database.session.add(user)
        database.session.refresh(user)
        
        # Create access token for the test user
        access_token = create_access_token(
            identity=user.id,
            additional_claims={
                'tenant_id': user.tenant_id,
                'user_id': user.id,
                'role': user.role
            }
        )
        
        return {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }


# Additional fixtures for CRM tests
@pytest.fixture
def test_tenant(app):
    """Create a test tenant for CRM tests."""
    with app.app_context():
        tenant = Tenant(
            name="CRM Test Tenant",
            domain="crm-test.example.com",
            slug="crm-test-tenant",
            settings={"test": True}
        )
        database.session.add(tenant)
        database.session.commit()
        return tenant


@pytest.fixture
def test_user(app, test_tenant):
    """Create a test user for CRM tests."""
    with app.app_context():
        user = User(
            tenant_id=test_tenant.id,
            email="crm-test@example.com",
            password_hash="hashed_password",
            first_name="CRM",
            last_name="Tester",
            role="manager",
            is_active=True
        )
        database.session.add(user)
        database.session.commit()
        return user