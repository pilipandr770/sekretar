"""Tests for German insolvency monitoring functionality."""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app import create_app, db
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, KYBAlert, KYBMonitoringConfig
)
from app.models.tenant import Tenant
from app.models.user import User
from app.services.kyb_adapters.insolvency_de import GermanInsolvencyAdapter
from app.services.insolvency_service import InsolvencyMonitoringService
from app.utils.exceptions import KYBError


@pytest.fixture
def app():
    """Create test app."""
    app = create_app('testing')
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def tenant(app):
    """Create test tenant."""
    tenant = Tenant.create(
        name="Test Company",
        domain="test.com",
        settings={}
    )
    return tenant


@pytest.fixture
def user(app, tenant):
    """Create test user."""
    user = User.create(
        tenant_id=tenant.id,
        email="test@test.com",
        password="password123",
        role="owner",
        is_active=True
    )
    return user


@pytest.fixture
def german_counterparty(app, tenant):
    """Create German counterparty for testing."""
    counterparty = Counterparty.create(
        tenant_id=tenant.id,
        name="Test GmbH",
        vat_number="DE123456789",
        registration_number="HRB 12345",
        country_code="DE",
        city="München",
        postal_code="80331",
        address="Teststraße 1",
        monitoring_enabled=True
    )
    return counterparty


@pytest.fixture
def kyb_config(app, tenant):
    """Create KYB monitoring config."""
    config = KYBMonitoringConfig.create(
        tenant_id=tenant.id,
        insolvency_de_enabled=True,
        alert_on_insolvency=True
    )
    return config


class TestGermanInsolvencyAdapter:
    """Test German insolvency adapter."""
    
    def test_adapter_initialization(self):
        """Test adapter initialization."""
        adapter = GermanInsolvencyAdapter()
        
        assert adapter.source_name == 'GERMANINSOLVENCY'
        assert adapter.RATE_LIMIT == 30
        assert adapter.CACHE_TTL == 3600
        assert adapter.BASE_URL == "https://www.insolvenzbekanntmachungen.de"
    
    def test_validate_identifier(self):
        """Test identifier validation."""
        adapter = GermanInsolvencyAdapter()
        
        # Valid company names
        assert adapter._validate_identifier("Test GmbH") == "Test GmbH"
        assert adapter._validate_identifier("  Example AG  ") == "Example AG"
        assert adapter._validate_identifier("Company KG") == "Company KG"
        
        # Empty identifier should raise error
        with pytest.raises(Exception):
            adapter._validate_identifier("")
        
        with pytest.raises(Exception):
            adapter._validate_identifier("   ")
    
    def test_prepare_search_params(self):
        """Test search parameter preparation."""
        adapter = GermanInsolvencyAdapter()
        
        params = adapter._prepare_search_params(
            "Test GmbH",
            registration_number="HRB 12345",
            city="München",
            postal_code="80331"
        )
        
        assert params['suchTyp'] == 'SCHULDNER'
        assert params['schuldnerName'] == 'Test GmbH'
        assert params['registerNummer'] == 'HRB 12345'
        assert params['ort'] == 'München'
        assert params['plz'] == '80331'
        assert 'datumVon' in params
        assert 'datumBis' in params
    
    def test_extract_company_name(self):
        """Test company name extraction from text."""
        adapter = GermanInsolvencyAdapter()
        
        # Test various patterns
        text1 = "Firma: Test GmbH, München"
        assert adapter._extract_company_name(text1) == "Test GmbH"
        
        text2 = "Schuldner: Example AG"
        assert adapter._extract_company_name(text2) == "Example AG"
        
        text3 = "Some text with Company KG in the middle"
        assert adapter._extract_company_name(text3) == "Company KG"
    
    def test_extract_proceeding_type(self):
        """Test proceeding type extraction."""
        adapter = GermanInsolvencyAdapter()
        
        assert adapter._extract_proceeding_type("Eröffnung des Verfahrens") == "opening"
        assert adapter._extract_proceeding_type("Einstellung mangels Masse") == "termination"
        assert adapter._extract_proceeding_type("Aufhebung des Verfahrens") == "cancellation"
        assert adapter._extract_proceeding_type("Antrag gestellt") == "application"
        assert adapter._extract_proceeding_type("Unknown text") == "unknown"
    
    def test_extract_court(self):
        """Test court name extraction."""
        adapter = GermanInsolvencyAdapter()
        
        text1 = "Amtsgericht München"
        assert adapter._extract_court(text1) == "Amtsgericht München"
        
        text2 = "AG Berlin"
        assert adapter._extract_court(text2) == "AG Berlin"
        
        text3 = "Landgericht Hamburg"
        assert adapter._extract_court(text3) == "Landgericht Hamburg"
    
    def test_extract_case_number(self):
        """Test case number extraction."""
        adapter = GermanInsolvencyAdapter()
        
        text1 = "Az.: 12 IN 345/23"
        assert "12 IN 345/23" in adapter._extract_case_number(text1)
        
        text2 = "Aktenzeichen: 5 HRB 678/22"
        assert "5 HRB 678/22" in adapter._extract_case_number(text2)
    
    def test_extract_date(self):
        """Test date extraction."""
        adapter = GermanInsolvencyAdapter()
        
        text1 = "Datum: 15.03.2024"
        assert adapter._extract_date(text1) == "2024-03-15"
        
        text2 = "2024-03-15"
        assert adapter._extract_date(text2) == "2024-03-15"
    
    def test_extract_status(self):
        """Test status extraction."""
        adapter = GermanInsolvencyAdapter()
        
        assert adapter._extract_status("Verfahren eröffnet") == "opened"
        assert adapter._extract_status("Verfahren eingestellt") == "terminated"
        assert adapter._extract_status("Verfahren aufgehoben") == "cancelled"
        assert adapter._extract_status("Antrag beantragt") == "applied"
        assert adapter._extract_status("Unknown status") == "unknown"
    
    def test_is_relevant_result(self):
        """Test relevance checking."""
        adapter = GermanInsolvencyAdapter()
        
        # Exact company name match
        assert adapter._is_relevant_result("Test GmbH insolvency", "Test GmbH")
        
        # Partial match
        assert adapter._is_relevant_result("Test Company GmbH", "Test")
        
        # Insolvency keywords
        assert adapter._is_relevant_result("Insolvenzverfahren eröffnet", "Unknown")
        
        # Irrelevant text
        assert not adapter._is_relevant_result("Random text", "Test GmbH")
    
    @patch('requests.Session.get')
    def test_search_insolvency_proceedings_success(self, mock_get):
        """Test successful insolvency search."""
        adapter = GermanInsolvencyAdapter()
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = """
        <html>
            <body>
                <div class="result">
                    Test GmbH - Insolvenzverfahren eröffnet
                    Amtsgericht München, Az.: 12 IN 345/23
                    Datum: 15.03.2024
                </div>
            </body>
        </html>
        """
        mock_get.return_value = mock_response
        
        result = adapter._search_insolvency_proceedings("Test GmbH")
        
        assert result['status'] in ['found', 'not_found']
        assert 'proceedings_found' in result
        assert 'proceedings' in result
    
    @patch('requests.Session.get')
    def test_search_insolvency_proceedings_timeout(self, mock_get):
        """Test insolvency search timeout."""
        adapter = GermanInsolvencyAdapter()
        
        # Mock timeout
        mock_get.side_effect = Exception("Timeout")
        
        result = adapter._search_insolvency_proceedings("Test GmbH")
        
        assert result['status'] == 'error'
        assert 'error' in result
        assert result['proceedings_found'] is False
    
    @patch('requests.Session.get')
    def test_check_single_with_cache(self, mock_get):
        """Test single check with caching."""
        # Mock Redis client
        mock_redis = Mock()
        
        # Mock rate limit check (return None for first call, then return cached data)
        def mock_get_side_effect(key):
            if 'rate_limit' in key:
                return None  # No rate limit hit
            elif 'cache' in key:
                return json.dumps({
                    'status': 'found',
                    'proceedings_found': True,
                    'proceedings': []
                })
            return None
        
        mock_redis.get.side_effect = mock_get_side_effect
        mock_redis.setex.return_value = True
        
        adapter = GermanInsolvencyAdapter(redis_client=mock_redis)
        
        result = adapter.check_single("Test GmbH")
        
        # Should return cached result without making HTTP request
        assert not mock_get.called
        assert result['status'] == 'found'
        assert result['proceedings_found'] is True


class TestInsolvencyMonitoringService:
    """Test insolvency monitoring service."""
    
    def test_service_initialization(self):
        """Test service initialization."""
        service = InsolvencyMonitoringService()
        assert isinstance(service.adapter, GermanInsolvencyAdapter)
    
    def test_check_counterparty_insolvency_non_german(self, app, german_counterparty):
        """Test insolvency check for non-German counterparty."""
        with app.app_context():
            # Change country to non-German
            german_counterparty.country_code = 'FR'
            german_counterparty.save()
            
            service = InsolvencyMonitoringService()
            result = service.check_counterparty_insolvency(german_counterparty.id)
            
            assert result['status'] == 'skipped'
            assert result['reason'] == 'not_german_company'
            assert result['country_code'] == 'FR'
    
    def test_check_counterparty_insolvency_not_found(self, app):
        """Test insolvency check for non-existent counterparty."""
        with app.app_context():
            service = InsolvencyMonitoringService()
            
            with pytest.raises(KYBError):
                service.check_counterparty_insolvency(99999)
    
    @patch('app.services.insolvency_service.GermanInsolvencyAdapter')
    def test_check_counterparty_insolvency_success(self, mock_adapter_class, app, german_counterparty, kyb_config):
        """Test successful insolvency check."""
        with app.app_context():
            # Mock adapter
            mock_adapter = Mock()
            mock_adapter.check_single.return_value = {
                'status': 'found',
                'proceedings_found': True,
                'proceedings_count': 1,
                'proceedings': [{
                    'company_name': 'Test GmbH',
                    'proceeding_type': 'opening',
                    'court': 'Amtsgericht München',
                    'case_number': '12 IN 345/23',
                    'date': '2024-03-15',
                    'status': 'opened'
                }],
                'source': 'INSOLVENCY_DE',
                'checked_at': datetime.utcnow().isoformat(),
                'response_time_ms': 1500
            }
            mock_adapter_class.return_value = mock_adapter
            
            service = InsolvencyMonitoringService()
            result = service.check_counterparty_insolvency(german_counterparty.id)
            
            assert result['counterparty_id'] == german_counterparty.id
            assert result['counterparty_name'] == german_counterparty.name
            assert result['check_result']['proceedings_found'] is True
            assert result['check_result']['proceedings_count'] == 1
            assert result['snapshot_id'] is not None
    
    def test_batch_check_insolvency(self, app, tenant):
        """Test batch insolvency checking."""
        with app.app_context():
            # Create multiple German counterparties
            counterparties = []
            for i in range(3):
                cp = Counterparty.create(
                    tenant_id=tenant.id,
                    name=f"Test Company {i} GmbH",
                    country_code="DE",
                    monitoring_enabled=True
                )
                counterparties.append(cp)
            
            service = InsolvencyMonitoringService()
            
            with patch.object(service, 'check_counterparty_insolvency') as mock_check:
                mock_check.return_value = {
                    'counterparty_id': 1,
                    'status': 'checked',
                    'proceedings_found': False
                }
                
                counterparty_ids = [cp.id for cp in counterparties]
                results = service.batch_check_insolvency(counterparty_ids)
                
                assert len(results) == 3
                assert mock_check.call_count == 3
    
    def test_get_insolvency_summary(self, app, tenant, german_counterparty):
        """Test insolvency summary generation."""
        with app.app_context():
            service = InsolvencyMonitoringService()
            summary = service.get_insolvency_summary(tenant.id)
            
            assert 'tenant_id' in summary
            assert 'total_german_counterparties' in summary
            assert 'recent_checks' in summary
            assert 'proceedings_found' in summary
            assert 'active_proceedings' in summary
            assert 'recent_alerts' in summary
    
    def test_analyze_proceedings_risk(self, app):
        """Test proceedings risk analysis."""
        with app.app_context():
            service = InsolvencyMonitoringService()
            
            # Test with active proceedings
            proceedings = [{
                'status': 'opened',
                'date': '2024-03-15'
            }]
            
            risk_analysis = service._analyze_proceedings_risk(proceedings)
            
            assert risk_analysis['risk_level'] == 'critical'
            assert risk_analysis['active_proceedings'] == 1
            assert risk_analysis['risk_score'] >= 80
            assert 'Active insolvency proceeding' in str(risk_analysis['risk_factors'])
    
    def test_create_insolvency_snapshot(self, app, german_counterparty):
        """Test snapshot creation."""
        with app.app_context():
            service = InsolvencyMonitoringService()
            
            result = {
                'counterparty_id': german_counterparty.id,
                'status': 'found',
                'proceedings_found': True,
                'proceedings_count': 1,
                'source': 'INSOLVENCY_DE'
            }
            
            snapshot = service._create_insolvency_snapshot(german_counterparty, result)
            
            assert snapshot is not None
            assert snapshot.counterparty_id == german_counterparty.id
            assert snapshot.check_type == 'insolvency_de'
            assert snapshot.source == 'INSOLVENCY_DE'
            assert snapshot.processed_data == result
    
    def test_check_for_new_proceedings_first_time(self, app, german_counterparty):
        """Test new proceedings detection on first check."""
        with app.app_context():
            service = InsolvencyMonitoringService()
            
            # Create snapshot with proceedings
            result = {
                'proceedings_found': True,
                'proceedings': [{
                    'case_number': '12 IN 345/23',
                    'status': 'opened'
                }]
            }
            
            snapshot = service._create_insolvency_snapshot(german_counterparty, result)
            
            with patch.object(service, '_generate_insolvency_alert') as mock_alert:
                service._check_for_new_proceedings(german_counterparty, snapshot)
                
                # Should generate alert for first-time proceedings
                mock_alert.assert_called_once()
                args = mock_alert.call_args[0]
                assert args[2] == 'new_insolvency_detected'
    
    def test_generate_insolvency_alert(self, app, german_counterparty):
        """Test insolvency alert generation."""
        with app.app_context():
            service = InsolvencyMonitoringService()
            
            # Create snapshot
            result = {'proceedings_found': True}
            snapshot = service._create_insolvency_snapshot(german_counterparty, result)
            
            service._generate_insolvency_alert(
                german_counterparty,
                snapshot,
                'new_insolvency_detected',
                'Test alert message'
            )
            
            # Check alert was created
            alert = KYBAlert.query.filter_by(
                counterparty_id=german_counterparty.id,
                alert_type='insolvency_detected'
            ).first()
            
            assert alert is not None
            assert alert.severity == 'high'
            assert alert.message == 'Test alert message'
            assert alert.alert_data['alert_subtype'] == 'new_insolvency_detected'


class TestInsolvencyAPIEndpoints:
    """Test insolvency API endpoints."""
    
    def get_auth_headers(self, user):
        """Get authentication headers for user."""
        from flask_jwt_extended import create_access_token
        token = create_access_token(identity=user.id)
        return {'Authorization': f'Bearer {token}'}
    
    def test_check_counterparty_insolvency_endpoint(self, client, app, user, german_counterparty):
        """Test manual insolvency check endpoint."""
        with app.app_context():
            headers = self.get_auth_headers(user)
            
            with patch('app.services.insolvency_service.InsolvencyMonitoringService') as mock_service_class:
                mock_service = Mock()
                mock_service.check_counterparty_insolvency.return_value = {
                    'counterparty_id': german_counterparty.id,
                    'status': 'checked',
                    'proceedings_found': False
                }
                mock_service_class.return_value = mock_service
                
                response = client.post(
                    f'/api/v1/kyb/insolvency/check/{german_counterparty.id}',
                    headers=headers
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert 'data' in data
    
    def test_batch_check_insolvency_endpoint(self, client, app, user, tenant):
        """Test batch insolvency check endpoint."""
        with app.app_context():
            # Create counterparties
            counterparties = []
            for i in range(2):
                cp = Counterparty.create(
                    tenant_id=tenant.id,
                    name=f"Test Company {i} GmbH",
                    country_code="DE"
                )
                counterparties.append(cp)
            
            headers = self.get_auth_headers(user)
            counterparty_ids = [cp.id for cp in counterparties]
            
            with patch('app.services.insolvency_service.InsolvencyMonitoringService') as mock_service_class:
                mock_service = Mock()
                mock_service.batch_check_insolvency.return_value = [
                    {'counterparty_id': cp.id, 'status': 'checked'}
                    for cp in counterparties
                ]
                mock_service_class.return_value = mock_service
                
                response = client.post(
                    '/api/v1/kyb/insolvency/batch-check',
                    headers=headers,
                    json={'counterparty_ids': counterparty_ids}
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['data']['total_checked'] == 2
    
    def test_get_insolvency_summary_endpoint(self, client, app, user):
        """Test insolvency summary endpoint."""
        with app.app_context():
            headers = self.get_auth_headers(user)
            
            with patch('app.services.insolvency_service.InsolvencyMonitoringService') as mock_service_class:
                mock_service = Mock()
                mock_service.get_insolvency_summary.return_value = {
                    'tenant_id': user.tenant_id,
                    'total_german_counterparties': 5,
                    'proceedings_found': 2,
                    'active_proceedings': 1
                }
                mock_service_class.return_value = mock_service
                
                response = client.get(
                    '/api/v1/kyb/insolvency/summary',
                    headers=headers
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['data']['total_german_counterparties'] == 5
    
    def test_get_proceeding_details_endpoint(self, client, app, user):
        """Test proceeding details endpoint."""
        with app.app_context():
            headers = self.get_auth_headers(user)
            case_number = "12 IN 345/23"
            
            with patch('app.services.insolvency_service.InsolvencyMonitoringService') as mock_service_class:
                mock_service = Mock()
                mock_service.get_proceeding_details.return_value = {
                    'case_number': case_number,
                    'status': 'found',
                    'details': {}
                }
                mock_service_class.return_value = mock_service
                
                response = client.get(
                    f'/api/v1/kyb/insolvency/proceeding/{case_number}',
                    headers=headers
                )
                
                assert response.status_code == 200
                data = json.loads(response.data)
                assert data['success'] is True
                assert data['data']['case_number'] == case_number
    
    def test_unauthorized_access(self, client, app, german_counterparty):
        """Test unauthorized access to insolvency endpoints."""
        with app.app_context():
            # Test without authentication
            response = client.post(f'/api/v1/kyb/insolvency/check/{german_counterparty.id}')
            assert response.status_code == 401
            
            response = client.post('/api/v1/kyb/insolvency/batch-check')
            assert response.status_code == 401
            
            response = client.get('/api/v1/kyb/insolvency/summary')
            assert response.status_code == 401


class TestInsolvencyWorkerIntegration:
    """Test insolvency monitoring integration with KYB worker."""
    
    @patch('app.services.insolvency_service.InsolvencyMonitoringService')
    def test_kyb_worker_insolvency_check(self, mock_service_class, app, german_counterparty, kyb_config):
        """Test insolvency check integration in KYB worker."""
        with app.app_context():
            from app.workers.kyb_monitoring import _perform_data_check
            
            # Mock service
            mock_service = Mock()
            mock_service.check_counterparty_insolvency.return_value = {
                'check_result': {
                    'status': 'found',
                    'proceedings_found': True,
                    'proceedings_count': 1,
                    'proceedings': [],
                    'risk_analysis': {'risk_level': 'high'},
                    'response_time_ms': 1500
                }
            }
            mock_service_class.return_value = mock_service
            
            result = _perform_data_check(german_counterparty, 'insolvency_de', kyb_config)
            
            assert result['status'] == 'found'
            assert result['proceedings_found'] is True
            assert result['proceedings_count'] == 1
            assert result['source'] == 'INSOLVENCY_DE'
            assert result['response_time_ms'] == 1500
    
    def test_determine_check_types_includes_insolvency(self, app, german_counterparty, kyb_config):
        """Test that insolvency check is included for German counterparties."""
        with app.app_context():
            from app.workers.kyb_monitoring import _determine_check_types
            
            check_types = _determine_check_types(german_counterparty, kyb_config)
            
            assert 'insolvency_de' in check_types
    
    def test_determine_check_types_excludes_non_german(self, app, german_counterparty, kyb_config):
        """Test that insolvency check is excluded for non-German counterparties."""
        with app.app_context():
            from app.workers.kyb_monitoring import _determine_check_types
            
            # Change to non-German
            german_counterparty.country_code = 'FR'
            
            check_types = _determine_check_types(german_counterparty, kyb_config)
            
            assert 'insolvency_de' not in check_types
    
    def test_determine_check_types_disabled_config(self, app, german_counterparty, kyb_config):
        """Test that insolvency check is excluded when disabled in config."""
        with app.app_context():
            from app.workers.kyb_monitoring import _determine_check_types
            
            # Disable insolvency monitoring
            kyb_config.insolvency_de_enabled = False
            
            check_types = _determine_check_types(german_counterparty, kyb_config)
            
            assert 'insolvency_de' not in check_types


if __name__ == '__main__':
    pytest.main([__file__])