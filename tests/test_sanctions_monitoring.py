"""Tests for sanctions monitoring functionality."""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

from app import create_app, db
from app.models.kyb_monitoring import Counterparty, CounterpartySnapshot, KYBAlert, KYBMonitoringConfig
from app.models.tenant import Tenant
from app.services.sanctions_service import SanctionsMonitoringService
from app.services.kyb_adapters.sanctions_eu import EUSanctionsAdapter
from app.services.kyb_adapters.sanctions_ofac import OFACSanctionsAdapter
from app.services.kyb_adapters.sanctions_uk import UKSanctionsAdapter
from app.services.kyb_adapters.base import ValidationError, DataSourceUnavailable, RateLimitExceeded
from app.workers.kyb_monitoring import (
    check_counterparty_sanctions, batch_check_sanctions, 
    generate_sanctions_alerts, update_sanctions_data,
    schedule_sanctions_monitoring
)


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
    tenant = Tenant(
        name="Test Company",
        domain="test.com",
        settings={}
    )
    db.session.add(tenant)
    db.session.commit()
    return tenant


@pytest.fixture
def counterparty(app, tenant):
    """Create test counterparty."""
    counterparty = Counterparty(
        tenant_id=tenant.id,
        name="SBERBANK OF RUSSIA",
        vat_number="RU1234567890",
        country_code="RU",
        monitoring_enabled=True
    )
    db.session.add(counterparty)
    db.session.commit()
    return counterparty


@pytest.fixture
def kyb_config(app, tenant):
    """Create test KYB monitoring configuration."""
    config = KYBMonitoringConfig(
        tenant_id=tenant.id,
        sanctions_eu_enabled=True,
        sanctions_ofac_enabled=True,
        sanctions_uk_enabled=True
    )
    db.session.add(config)
    db.session.commit()
    return config


class TestEUSanctionsAdapter:
    """Test EU sanctions adapter."""
    
    def test_init(self):
        """Test adapter initialization."""
        adapter = EUSanctionsAdapter()
        assert adapter.source_name == 'EUSANCTIONS'
        assert adapter.rate_limit == 100
        assert adapter.cache_ttl == 7200
    
    def test_validate_entity_name_valid(self):
        """Test entity name validation with valid input."""
        adapter = EUSanctionsAdapter()
        result = adapter._validate_entity_name("Test Company Ltd")
        assert result == "Test Company Ltd"
    
    def test_validate_entity_name_empty(self):
        """Test entity name validation with empty input."""
        adapter = EUSanctionsAdapter()
        with pytest.raises(ValidationError, match="Entity name cannot be empty"):
            adapter._validate_entity_name("")
    
    def test_validate_entity_name_too_short(self):
        """Test entity name validation with too short input."""
        adapter = EUSanctionsAdapter()
        with pytest.raises(ValidationError, match="Entity name must be at least 3 characters"):
            adapter._validate_entity_name("AB")
    
    def test_check_single_no_match(self):
        """Test checking entity with no sanctions match."""
        adapter = EUSanctionsAdapter()
        result = adapter.check_single("Clean Company Ltd")
        
        assert result['status'] == 'no_match'
        assert result['risk_level'] == 'low'
        assert result['total_matches'] == 0
        assert result['matches'] == []
        assert 'response_time_ms' in result
        assert 'checked_at' in result
    
    def test_check_single_with_match(self):
        """Test checking entity with sanctions match."""
        adapter = EUSanctionsAdapter()
        result = adapter.check_single("SBERBANK OF RUSSIA")
        
        assert result['status'] == 'match'
        assert result['risk_level'] == 'critical'
        assert result['total_matches'] > 0
        assert len(result['matches']) > 0
        
        # Check match details
        match = result['matches'][0]
        assert 'matched_name' in match
        assert 'similarity_score' in match
        assert 'sanctions_program' in match
    
    def test_check_batch(self):
        """Test batch checking functionality."""
        adapter = EUSanctionsAdapter()
        entities = ["Clean Company", "SBERBANK", "Another Clean Company"]
        results = adapter.check_batch(entities)
        
        assert len(results) == 3
        assert all('status' in result for result in results)
        
        # Should have one match (SBERBANK)
        matches = [r for r in results if r['status'] == 'match']
        assert len(matches) == 1
    
    def test_get_sanctions_info(self):
        """Test getting sanctions information."""
        adapter = EUSanctionsAdapter()
        info = adapter.get_sanctions_info()
        
        assert info['source'] == 'European Union Consolidated Sanctions List'
        assert 'url' in info
        assert 'entity_types' in info
        assert 'match_types' in info


class TestOFACSanctionsAdapter:
    """Test OFAC sanctions adapter."""
    
    def test_init(self):
        """Test adapter initialization."""
        adapter = OFACSanctionsAdapter()
        assert adapter.source_name == 'OFACSANCTIONS'
        assert adapter.rate_limit == 50
        assert adapter.cache_ttl == 7200
    
    def test_check_single_with_match(self):
        """Test checking entity with OFAC sanctions match."""
        adapter = OFACSanctionsAdapter()
        result = adapter.check_single("VLADIMIR PUTIN")
        
        assert result['status'] == 'match'
        assert result['risk_level'] == 'critical'
        assert result['total_matches'] > 0
        
        # Check match details
        match = result['matches'][0]
        assert 'ofac_uid' in match
        assert 'sanctions_program' in match
        assert 'entity_type' in match
    
    def test_calculate_similarity(self):
        """Test similarity calculation."""
        adapter = OFACSanctionsAdapter()
        
        # Exact match
        similarity = adapter._calculate_similarity("SBERBANK", "SBERBANK")
        assert similarity == 1.0
        
        # Partial match
        similarity = adapter._calculate_similarity("SBERBANK OF RUSSIA", "SBERBANK")
        assert similarity > 0.5
        
        # No match
        similarity = adapter._calculate_similarity("CLEAN COMPANY", "SBERBANK")
        assert similarity == 0.0
    
    def test_get_sanctions_programs(self):
        """Test getting OFAC sanctions programs."""
        adapter = OFACSanctionsAdapter()
        programs = adapter.get_sanctions_programs()
        
        assert len(programs) > 0
        assert all('code' in program for program in programs)
        assert all('name' in program for program in programs)
    
    def test_search_by_program(self):
        """Test searching by OFAC program."""
        adapter = OFACSanctionsAdapter()
        result = adapter.search_by_program('UKRAINE-EO13662')
        
        assert 'program_code' in result
        assert 'total_results' in result
        assert 'results' in result


class TestUKSanctionsAdapter:
    """Test UK sanctions adapter."""
    
    def test_init(self):
        """Test adapter initialization."""
        adapter = UKSanctionsAdapter()
        assert adapter.source_name == 'UKSANCTIONS'
        assert adapter.rate_limit == 60
        assert adapter.cache_ttl == 7200
    
    def test_check_single_with_match(self):
        """Test checking entity with UK sanctions match."""
        adapter = UKSanctionsAdapter()
        result = adapter.check_single("GAZPROM")
        
        assert result['status'] == 'match'
        assert result['risk_level'] == 'critical'
        assert result['total_matches'] > 0
        
        # Check match details
        match = result['matches'][0]
        assert 'uk_unique_id' in match
        assert 'sanctions_regime' in match
        assert 'sanctions_imposed' in match
    
    def test_get_sanctions_regimes(self):
        """Test getting UK sanctions regimes."""
        adapter = UKSanctionsAdapter()
        regimes = adapter.get_sanctions_regimes()
        
        assert len(regimes) > 0
        assert all('code' in regime for regime in regimes)
        assert all('name' in regime for regime in regimes)
    
    def test_get_entity_details(self):
        """Test getting entity details."""
        adapter = UKSanctionsAdapter()
        details = adapter.get_entity_details('RUS0001')
        
        assert 'uk_unique_id' in details
        assert 'name' in details
        assert 'entity_type' in details


class TestSanctionsMonitoringService:
    """Test sanctions monitoring service."""
    
    def test_init(self):
        """Test service initialization."""
        service = SanctionsMonitoringService()
        assert 'EU' in service.adapters
        assert 'OFAC' in service.adapters
        assert 'UK' in service.adapters
    
    def test_check_entity_all_sources_no_match(self, app, tenant, kyb_config):
        """Test checking entity against all sources with no matches."""
        service = SanctionsMonitoringService()
        result = service.check_entity_all_sources("Clean Company Ltd", tenant.id)
        
        assert result['status'] == 'no_match'
        assert result['risk_level'] == 'low'
        assert result['total_matches'] == 0
        assert len(result['sources_checked']) == 3
    
    def test_check_entity_all_sources_with_matches(self, app, tenant, kyb_config):
        """Test checking entity against all sources with matches."""
        service = SanctionsMonitoringService()
        result = service.check_entity_all_sources("SBERBANK", tenant.id)
        
        assert result['status'] == 'match'
        assert result['risk_level'] == 'critical'
        assert result['total_matches'] > 0
        assert len(result['matches']) > 0
    
    def test_check_counterparty_sanctions(self, app, counterparty, kyb_config):
        """Test checking counterparty sanctions."""
        service = SanctionsMonitoringService()
        result = service.check_counterparty_sanctions(counterparty.id)
        
        assert 'entity_name' in result
        assert 'status' in result
        assert 'sources_checked' in result
        assert result['entity_name'] == counterparty.name
    
    def test_batch_check_counterparties(self, app, tenant, kyb_config):
        """Test batch checking counterparties."""
        # Create multiple counterparties
        counterparties = []
        for i, name in enumerate(["Clean Company", "SBERBANK", "Another Company"]):
            cp = Counterparty(
                tenant_id=tenant.id,
                name=name,
                monitoring_enabled=True
            )
            db.session.add(cp)
            db.session.flush()
            counterparties.append(cp)
        db.session.commit()
        
        service = SanctionsMonitoringService()
        results = service.batch_check_counterparties([cp.id for cp in counterparties])
        
        assert len(results) == 3
        assert all('status' in result for result in results)
    
    def test_get_sanctions_statistics(self, app, tenant, counterparty, kyb_config):
        """Test getting sanctions statistics."""
        # Create some test snapshots
        snapshot = CounterpartySnapshot(
            tenant_id=tenant.id,
            counterparty_id=counterparty.id,
            source='EU',
            check_type='sanctions_eu',
            data_hash='test_hash',
            raw_data={'status': 'match'},
            status='match'
        )
        db.session.add(snapshot)
        
        # Create test alert
        alert = KYBAlert(
            tenant_id=tenant.id,
            counterparty_id=counterparty.id,
            alert_type='sanctions_match',
            severity='critical',
            title='Test Alert',
            message='Test message'
        )
        db.session.add(alert)
        db.session.commit()
        
        service = SanctionsMonitoringService()
        stats = service.get_sanctions_statistics(tenant.id)
        
        assert 'total_sanctions_checks' in stats
        assert 'matches_found' in stats
        assert 'alerts_generated' in stats
        assert stats['total_sanctions_checks'] >= 1
        assert stats['matches_found'] >= 1
        assert stats['alerts_generated'] >= 1


class TestSanctionsWorkerTasks:
    """Test sanctions monitoring worker tasks."""
    
    @patch('app.workers.kyb_monitoring.SanctionsMonitoringService')
    def test_check_counterparty_sanctions_task(self, mock_service_class, app, counterparty):
        """Test counterparty sanctions check task."""
        # Mock the service
        mock_service = Mock()
        mock_service.check_counterparty_sanctions.return_value = {
            'status': 'match',
            'total_matches': 1,
            'matches': [{'source': 'EU', 'matched_name': 'SBERBANK'}]
        }
        mock_service_class.return_value = mock_service
        
        # Run the task
        result = check_counterparty_sanctions(counterparty.id)
        
        assert result['status'] == 'match'
        assert result['total_matches'] == 1
        mock_service.check_counterparty_sanctions.assert_called_once_with(counterparty.id)
    
    @patch('app.workers.kyb_monitoring.SanctionsMonitoringService')
    def test_batch_check_sanctions_task(self, mock_service_class, app, tenant):
        """Test batch sanctions check task."""
        # Create test counterparties
        counterparties = []
        for name in ["Company A", "Company B"]:
            cp = Counterparty(tenant_id=tenant.id, name=name, monitoring_enabled=True)
            db.session.add(cp)
            db.session.flush()
            counterparties.append(cp)
        db.session.commit()
        
        # Mock the service
        mock_service = Mock()
        mock_service.batch_check_counterparties.return_value = [
            {'counterparty_id': counterparties[0].id, 'status': 'no_match', 'total_matches': 0},
            {'counterparty_id': counterparties[1].id, 'status': 'match', 'total_matches': 1}
        ]
        mock_service_class.return_value = mock_service
        
        # Run the task
        result = batch_check_sanctions([cp.id for cp in counterparties])
        
        assert result['total_checked'] == 2
        assert result['total_matches'] == 1
        mock_service.batch_check_counterparties.assert_called_once()
    
    def test_generate_sanctions_alerts_task(self, app, counterparty):
        """Test sanctions alerts generation task."""
        matches = [
            {
                'source': 'EU',
                'matched_name': 'SBERBANK',
                'similarity_score': 0.95,
                'sanctions_program': 'EU Restrictive Measures'
            }
        ]
        
        result = generate_sanctions_alerts(counterparty.id, matches)
        
        assert result['counterparty_id'] == counterparty.id
        assert result['matches_processed'] == 1
        assert len(result['alerts_created']) > 0
        
        # Check that alert was created in database
        alert = KYBAlert.query.filter_by(counterparty_id=counterparty.id).first()
        assert alert is not None
        assert alert.alert_type == 'sanctions_match'
        assert alert.severity == 'critical'
    
    @patch('app.workers.kyb_monitoring.SanctionsMonitoringService')
    def test_update_sanctions_data_task(self, mock_service_class, app):
        """Test sanctions data update task."""
        # Mock the service
        mock_service = Mock()
        mock_service.update_all_sanctions_data.return_value = {
            'sources_updated': ['EU', 'OFAC', 'UK'],
            'results': {
                'EU': {'success': True},
                'OFAC': {'success': True},
                'UK': {'success': True}
            }
        }
        mock_service_class.return_value = mock_service
        
        # Run the task
        result = update_sanctions_data()
        
        assert 'sources_updated' in result
        assert len(result['sources_updated']) == 3
        mock_service.update_all_sanctions_data.assert_called_once()
    
    def test_schedule_sanctions_monitoring_task(self, app, tenant, kyb_config):
        """Test sanctions monitoring scheduling task."""
        # Create test counterparties
        counterparties = []
        for i in range(3):
            cp = Counterparty(
                tenant_id=tenant.id,
                name=f"Company {i}",
                monitoring_enabled=True
            )
            db.session.add(cp)
            counterparties.append(cp)
        db.session.commit()
        
        with patch('app.workers.kyb_monitoring.batch_check_sanctions.apply_async') as mock_apply:
            mock_apply.return_value = Mock(id='task_123')
            
            result = schedule_sanctions_monitoring(tenant.id)
            
            assert result['total_counterparties'] >= 3
            assert result['counterparties_to_check'] >= 3
            assert result['batches_scheduled'] >= 1
            assert mock_apply.called


class TestSanctionsErrorHandling:
    """Test error handling in sanctions monitoring."""
    
    def test_adapter_validation_error(self):
        """Test handling of validation errors."""
        adapter = EUSanctionsAdapter()
        
        with pytest.raises(ValidationError):
            adapter.check_single("")
    
    @patch('app.services.kyb_adapters.sanctions_eu.requests.Session.post')
    def test_adapter_network_error(self, mock_post):
        """Test handling of network errors."""
        mock_post.side_effect = Exception("Network error")
        
        adapter = EUSanctionsAdapter()
        result = adapter.check_single("Test Company")
        
        assert result['status'] == 'error'
        assert 'Network error' in result['error']
    
    def test_service_invalid_counterparty(self, app):
        """Test service with invalid counterparty ID."""
        service = SanctionsMonitoringService()
        
        with pytest.raises(ValueError, match="Counterparty 999 not found"):
            service.check_counterparty_sanctions(999)
    
    def test_worker_task_error_handling(self, app):
        """Test worker task error handling."""
        # Test with invalid counterparty ID
        with pytest.raises(ValueError):
            check_counterparty_sanctions(999)


class TestSanctionsCaching:
    """Test sanctions monitoring caching functionality."""
    
    @patch('app.services.kyb_adapters.base.Redis')
    def test_cache_hit(self, mock_redis_class):
        """Test cache hit scenario."""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = json.dumps({
            'status': 'no_match',
            'total_matches': 0,
            'matches': []
        })
        mock_redis_class.return_value = mock_redis
        
        adapter = EUSanctionsAdapter(mock_redis)
        result = adapter.check_single("Test Company")
        
        assert result['cached'] is True
        assert result['status'] == 'no_match'
    
    @patch('app.services.kyb_adapters.base.Redis')
    def test_cache_miss(self, mock_redis_class):
        """Test cache miss scenario."""
        # Mock Redis client
        mock_redis = Mock()
        mock_redis.get.return_value = None
        mock_redis_class.return_value = mock_redis
        
        adapter = EUSanctionsAdapter(mock_redis)
        result = adapter.check_single("Clean Company")
        
        assert result['cached'] is False
        assert result['status'] == 'no_match'
        # Should have called setex to cache the result
        mock_redis.setex.assert_called()


class TestSanctionsIntegration:
    """Integration tests for sanctions monitoring."""
    
    def test_end_to_end_sanctions_check(self, app, tenant, counterparty, kyb_config):
        """Test complete end-to-end sanctions checking flow."""
        # Initialize service
        service = SanctionsMonitoringService()
        
        # Perform check
        result = service.check_counterparty_sanctions(counterparty.id)
        
        # Verify result structure
        assert 'entity_name' in result
        assert 'status' in result
        assert 'sources_checked' in result
        assert 'total_matches' in result
        
        # Check that snapshots were created
        snapshots = CounterpartySnapshot.query.filter_by(
            counterparty_id=counterparty.id
        ).all()
        assert len(snapshots) >= 3  # One for each source
        
        # If matches found, check that alerts were created
        if result['total_matches'] > 0:
            alerts = KYBAlert.query.filter_by(
                counterparty_id=counterparty.id,
                alert_type='sanctions_match'
            ).all()
            assert len(alerts) > 0
    
    def test_monitoring_configuration_impact(self, app, tenant, counterparty):
        """Test that monitoring configuration affects which sources are checked."""
        # Create config with only EU sanctions enabled
        config = KYBMonitoringConfig(
            tenant_id=tenant.id,
            sanctions_eu_enabled=True,
            sanctions_ofac_enabled=False,
            sanctions_uk_enabled=False
        )
        db.session.add(config)
        db.session.commit()
        
        service = SanctionsMonitoringService()
        result = service.check_counterparty_sanctions(counterparty.id)
        
        # Should only check EU source
        assert len(result['sources_checked']) == 1
        assert 'EU' in result['sources_checked']
        assert 'OFAC' not in result['sources_checked']
        assert 'UK' not in result['sources_checked']