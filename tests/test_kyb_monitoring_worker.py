"""Tests for KYB monitoring worker."""
import pytest
import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock
from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, CounterpartyDiff, 
    KYBAlert, KYBMonitoringConfig
)
from app.workers.kyb_monitoring import (
    collect_counterparty_data,
    detect_counterparty_changes,
    generate_kyb_alerts,
    create_evidence_snapshot,
    schedule_counterparty_monitoring,
    daily_kyb_monitoring,
    cleanup_old_kyb_data,
    _determine_check_types,
    _perform_data_check,
    _create_snapshot,
    _compare_snapshots,
    _assess_change_risk_impact,
    _calculate_risk_score_delta,
    _generate_alert_from_diff,
    _update_counterparty_risk_score,
    _calculate_next_check_time
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
def tenant(app):
    """Create test tenant."""
    tenant = Tenant(
        name="Test Company",
        domain="test.com",
        slug="test-company",
        settings={}
    )
    db.session.add(tenant)
    db.session.commit()
    return tenant


@pytest.fixture
def user(app, tenant):
    """Create test user."""
    user = User(
        tenant_id=tenant.id,
        email="test@test.com",
        password_hash="hashed",
        full_name="Test User",
        is_active=True
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def kyb_config(app, tenant):
    """Create KYB monitoring config."""
    config = KYBMonitoringConfig(
        tenant_id=tenant.id,
        vies_enabled=True,
        gleif_enabled=True,
        sanctions_eu_enabled=True,
        sanctions_ofac_enabled=True,
        sanctions_uk_enabled=True,
        insolvency_de_enabled=True,
        alert_on_sanctions_match=True,
        alert_on_vat_invalid=True,
        alert_on_lei_invalid=True,
        alert_on_insolvency=True,
        alert_on_data_change=True
    )
    db.session.add(config)
    db.session.commit()
    return config


@pytest.fixture
def counterparty(app, tenant):
    """Create test counterparty."""
    counterparty = Counterparty(
        tenant_id=tenant.id,
        name="Test Company Ltd",
        vat_number="DE123456789",
        lei_code="529900T8BM49AURSDO55",
        country_code="DE",
        address="Test Street 1, 12345 Berlin",
        monitoring_enabled=True,
        monitoring_frequency="daily",
        risk_score=25.0,
        risk_level="low"
    )
    db.session.add(counterparty)
    db.session.commit()
    return counterparty


class TestCollectCounterpartyData:
    """Test collect_counterparty_data task."""
    
    @patch('app.workers.kyb_monitoring.KYBService')
    def test_collect_counterparty_data_success(self, mock_kyb_service, app, counterparty, kyb_config):
        """Test successful data collection."""
        # Mock KYB service responses
        mock_kyb_service.check_vat_number.return_value = {
            'status': 'valid',
            'valid': True,
            'name': 'Test Company Ltd',
            'address': 'Test Street 1, 12345 Berlin',
            'source': 'VIES',
            'response_time_ms': 150,
            'checked_at': '2024-01-01T12:00:00Z'
        }
        
        mock_kyb_service.check_sanctions.return_value = []
        
        # Execute task
        result = collect_counterparty_data(counterparty.id)
        
        # Verify result
        assert result['counterparty_id'] == counterparty.id
        assert result['tenant_id'] == counterparty.tenant_id
        assert 'vat' in result['check_types']
        assert len(result['collection_results']) > 0
        assert len(result['snapshots_created']) > 0
        
        # Verify counterparty was updated
        db.session.refresh(counterparty)
        assert counterparty.last_checked is not None
        assert counterparty.next_check is not None
        
        # Verify snapshot was created
        snapshot = CounterpartySnapshot.query.filter_by(
            counterparty_id=counterparty.id
        ).first()
        assert snapshot is not None
        assert snapshot.check_type == 'vat'
        assert snapshot.status == 'valid'
    
    def test_collect_counterparty_data_not_found(self, app):
        """Test data collection for non-existent counterparty."""
        with pytest.raises(ValueError, match="Counterparty 999 not found"):
            collect_counterparty_data(999)
    
    def test_collect_counterparty_data_monitoring_disabled(self, app, counterparty, kyb_config):
        """Test data collection when monitoring is disabled."""
        counterparty.monitoring_enabled = False
        db.session.commit()
        
        result = collect_counterparty_data(counterparty.id)
        
        assert result['status'] == 'skipped'
        assert result['reason'] == 'monitoring_disabled'
    
    @patch('app.workers.kyb_monitoring.KYBService')
    def test_collect_counterparty_data_with_errors(self, mock_kyb_service, app, counterparty, kyb_config):
        """Test data collection with API errors."""
        # Mock KYB service to raise exception
        mock_kyb_service.check_vat_number.side_effect = Exception("API Error")
        mock_kyb_service.check_sanctions.return_value = []
        
        result = collect_counterparty_data(counterparty.id)
        
        # Should still return result with error info
        assert result['counterparty_id'] == counterparty.id
        assert len(result['collection_results']) > 0
        
        # Check that error was recorded
        error_result = next(
            (r for r in result['collection_results'] if r.get('status') == 'error'),
            None
        )
        assert error_result is not None
        assert 'API Error' in error_result['error']


class TestDetectCounterpartyChanges:
    """Test detect_counterparty_changes task."""
    
    def test_detect_counterparty_changes_success(self, app, counterparty):
        """Test successful change detection."""
        # Create old snapshot
        old_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='old_hash',
            raw_data={'status': 'valid', 'name': 'Old Company Name'},
            processed_data={'valid': True, 'company_name': 'Old Company Name'},
            status='valid'
        )
        db.session.add(old_snapshot)
        db.session.commit()
        
        # Create new snapshot with changes
        new_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='new_hash',
            raw_data={'status': 'valid', 'name': 'New Company Name'},
            processed_data={'valid': True, 'company_name': 'New Company Name'},
            status='valid'
        )
        db.session.add(new_snapshot)
        db.session.commit()
        
        # Execute task
        result = detect_counterparty_changes(counterparty.id, new_snapshot.id)
        
        # Verify result
        assert result['counterparty_id'] == counterparty.id
        assert result['new_snapshot_id'] == new_snapshot.id
        assert result['previous_snapshot_id'] == old_snapshot.id
        assert result['changes_detected'] == 1
        assert len(result['diffs_created']) == 1
        
        # Verify diff was created
        diff = CounterpartyDiff.query.filter_by(
            counterparty_id=counterparty.id
        ).first()
        assert diff is not None
        assert diff.field_path == 'company_name'
        assert diff.old_value == 'Old Company Name'
        assert diff.new_value == 'New Company Name'
        assert diff.change_type == 'modified'
    
    def test_detect_counterparty_changes_no_previous(self, app, counterparty):
        """Test change detection with no previous snapshot."""
        # Create only new snapshot
        new_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='new_hash',
            raw_data={'status': 'valid'},
            processed_data={'valid': True},
            status='valid'
        )
        db.session.add(new_snapshot)
        db.session.commit()
        
        result = detect_counterparty_changes(counterparty.id, new_snapshot.id)
        
        assert result['status'] == 'no_previous_snapshot'
        assert result['changes_detected'] == 0
    
    def test_detect_counterparty_changes_snapshot_not_found(self, app, counterparty):
        """Test change detection with non-existent snapshot."""
        with pytest.raises(ValueError, match="Snapshot 999 not found"):
            detect_counterparty_changes(counterparty.id, 999)


class TestGenerateKYBAlerts:
    """Test generate_kyb_alerts task."""
    
    def test_generate_kyb_alerts_from_diffs(self, app, counterparty, kyb_config):
        """Test alert generation from diffs."""
        # Create snapshots
        old_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='old_hash',
            raw_data={'status': 'valid'},
            processed_data={'valid': True},
            status='valid'
        )
        db.session.add(old_snapshot)
        db.session.flush()
        
        new_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='new_hash',
            raw_data={'status': 'invalid'},
            processed_data={'valid': False},
            status='invalid'
        )
        db.session.add(new_snapshot)
        db.session.flush()
        
        # Create diff
        diff = CounterpartyDiff(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            old_snapshot_id=old_snapshot.id,
            new_snapshot_id=new_snapshot.id,
            field_path='valid',
            old_value='True',
            new_value='False',
            change_type='modified',
            risk_impact='high',
            risk_score_delta=20.0,
            processed=False
        )
        db.session.add(diff)
        db.session.commit()
        
        # Execute task
        result = generate_kyb_alerts(counterparty.id)
        
        # Verify result
        assert result['counterparty_id'] == counterparty.id
        assert result['diffs_processed'] == 1
        assert result['alerts_generated'] >= 1
        
        # Verify alert was created
        alert = KYBAlert.query.filter_by(
            counterparty_id=counterparty.id
        ).first()
        assert alert is not None
        assert alert.alert_type == 'validation_failure'
        assert alert.severity == 'medium'
        
        # Verify diff was marked as processed
        db.session.refresh(diff)
        assert diff.processed is True
        assert diff.alert_generated is True
    
    def test_generate_kyb_alerts_high_risk_score(self, app, counterparty, kyb_config):
        """Test alert generation for high risk score."""
        # Set high risk score
        counterparty.risk_score = 85.0
        counterparty.risk_level = 'high'
        db.session.commit()
        
        result = generate_kyb_alerts(counterparty.id)
        
        # Should generate risk-based alert
        assert result['alerts_generated'] >= 1
        
        alert = KYBAlert.query.filter_by(
            counterparty_id=counterparty.id,
            alert_type='high_risk_score'
        ).first()
        assert alert is not None
        assert alert.severity == 'high'
    
    def test_generate_kyb_alerts_no_config(self, app, counterparty):
        """Test alert generation without config."""
        result = generate_kyb_alerts(counterparty.id)
        
        assert result['status'] == 'no_config'
        assert result['alerts_generated'] == 0


class TestCreateEvidenceSnapshot:
    """Test create_evidence_snapshot task."""
    
    def test_create_evidence_snapshot_success(self, app, counterparty):
        """Test successful evidence creation."""
        # Create snapshot
        snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='test_hash',
            raw_data={'status': 'valid', 'name': 'Test Company'},
            processed_data={'valid': True, 'company_name': 'Test Company'},
            status='valid'
        )
        db.session.add(snapshot)
        db.session.commit()
        
        with patch('app.workers.kyb_monitoring.current_app') as mock_app:
            # Mock config to use temp directory
            with tempfile.TemporaryDirectory() as temp_dir:
                mock_config = MagicMock()
                mock_config.get.return_value = temp_dir
                mock_app.config = mock_config
                
                result = create_evidence_snapshot(snapshot.id)
                
                # Verify result
                assert result['snapshot_id'] == snapshot.id
                assert result['counterparty_id'] == counterparty.id
                assert 'evidence_directory' in result
                assert len(result['evidence_files']) > 0
                
                # Verify snapshot was updated
                db.session.refresh(snapshot)
                assert snapshot.evidence_stored is True
                assert snapshot.evidence_path is not None
                
                # Verify files were created
                evidence_dir = result['evidence_directory']
                assert os.path.exists(evidence_dir)
                
                # Check for expected files
                files = os.listdir(evidence_dir)
                assert any('raw_response' in f for f in files)
                assert any('data_summary' in f for f in files)
                assert any('compliance_report' in f for f in files)
    
    def test_create_evidence_snapshot_not_found(self, app):
        """Test evidence creation for non-existent snapshot."""
        with pytest.raises(ValueError, match="Snapshot 999 not found"):
            create_evidence_snapshot(999)


class TestScheduleCounterpartyMonitoring:
    """Test schedule_counterparty_monitoring task."""
    
    @patch('app.workers.kyb_monitoring.collect_counterparty_data')
    def test_schedule_counterparty_monitoring_success(self, mock_collect, app, counterparty, kyb_config):
        """Test successful monitoring scheduling."""
        # Set counterparty to need checking
        counterparty.next_check = datetime.utcnow() - timedelta(hours=1)
        db.session.commit()
        
        # Mock task result
        mock_task = Mock()
        mock_task.id = 'task_123'
        mock_collect.apply_async.return_value = mock_task
        
        result = schedule_counterparty_monitoring(counterparty.tenant_id)
        
        # Verify result
        assert result['tenant_id'] == counterparty.tenant_id
        assert result['counterparties_checked'] == 1
        assert result['tasks_scheduled'] == 1
        assert result['scheduling_errors'] == 0
        assert len(result['scheduled_tasks']) == 1
        
        # Verify task was scheduled
        mock_collect.apply_async.assert_called_once_with(
            args=[counterparty.id],
            countdown=0
        )
    
    def test_schedule_counterparty_monitoring_no_counterparties(self, app, tenant):
        """Test scheduling with no counterparties needing checks."""
        result = schedule_counterparty_monitoring(tenant.id)
        
        assert result['counterparties_checked'] == 0
        assert result['tasks_scheduled'] == 0
    
    def test_schedule_counterparty_monitoring_disabled(self, app, counterparty, kyb_config):
        """Test scheduling with monitoring disabled."""
        counterparty.monitoring_enabled = False
        db.session.commit()
        
        result = schedule_counterparty_monitoring(counterparty.tenant_id)
        
        assert result['counterparties_checked'] == 0


class TestDailyKYBMonitoring:
    """Test daily_kyb_monitoring task."""
    
    @patch('app.workers.kyb_monitoring.schedule_counterparty_monitoring')
    def test_daily_kyb_monitoring_success(self, mock_schedule, app, kyb_config):
        """Test successful daily monitoring."""
        # Mock task result
        mock_task = Mock()
        mock_task.id = 'task_123'
        mock_schedule.apply_async.return_value = mock_task
        
        result = daily_kyb_monitoring()
        
        # Verify result
        assert result['tenants_processed'] == 1
        assert result['tasks_scheduled'] == 1
        assert result['errors'] == 0
        
        # Verify scheduling was called
        mock_schedule.apply_async.assert_called_once_with(
            args=[kyb_config.tenant_id],
            countdown=0
        )


class TestCleanupOldKYBData:
    """Test cleanup_old_kyb_data task."""
    
    def test_cleanup_old_kyb_data_success(self, app, counterparty):
        """Test successful data cleanup."""
        # Create old snapshots
        old_date = datetime.utcnow() - timedelta(days=400)
        
        old_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='old_hash',
            raw_data={'status': 'valid'},
            status='valid',
            created_at=old_date
        )
        db.session.add(old_snapshot)
        
        # Create old resolved alert
        old_alert = KYBAlert(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            alert_type='data_change',
            severity='low',
            title='Test Alert',
            message='Test message',
            status='resolved',
            created_at=old_date
        )
        db.session.add(old_alert)
        db.session.commit()
        
        result = cleanup_old_kyb_data(365)
        
        # Verify result
        assert result['retention_days'] == 365
        assert result['snapshots_deleted'] == 1
        assert result['alerts_deleted'] == 0  # Alert retention is 3x longer
        
        # Verify data was deleted
        assert CounterpartySnapshot.query.get(old_snapshot.id) is None
        assert KYBAlert.query.get(old_alert.id) is not None  # Should still exist


class TestHelperFunctions:
    """Test helper functions."""
    
    def test_determine_check_types(self, app, counterparty, kyb_config):
        """Test check type determination."""
        check_types = _determine_check_types(counterparty, kyb_config)
        
        # Should include VAT check (has VAT number and country)
        assert 'vat' in check_types
        
        # Should include LEI check (has LEI code)
        assert 'lei' in check_types
        
        # Should include sanctions checks (has name)
        assert 'sanctions_eu' in check_types
        assert 'sanctions_ofac' in check_types
        assert 'sanctions_uk' in check_types
        
        # Should include insolvency check (Germany + registration number)
        counterparty.registration_number = 'HRB123456'
        db.session.commit()
        
        check_types = _determine_check_types(counterparty, kyb_config)
        assert 'insolvency_de' in check_types
    
    def test_assess_change_risk_impact(self, app):
        """Test risk impact assessment."""
        # Critical risk - sanctions match found
        impact = _assess_change_risk_impact('matches_found', False, True)
        assert impact == 'critical'
        
        # High risk - validation failed
        impact = _assess_change_risk_impact('valid', True, False)
        assert impact == 'high'
        
        # Medium risk - company name change
        impact = _assess_change_risk_impact('company_name', 'Old Name', 'New Name')
        assert impact == 'medium'
        
        # Low risk - other changes
        impact = _assess_change_risk_impact('other_field', 'old', 'new')
        assert impact == 'low'
    
    def test_calculate_risk_score_delta(self, app):
        """Test risk score delta calculation."""
        # Sanctions match found
        delta = _calculate_risk_score_delta('matches_found', False, True)
        assert delta == 50.0
        
        # Insolvency found
        delta = _calculate_risk_score_delta('insolvency_found', False, True)
        assert delta == 40.0
        
        # Validation failed
        delta = _calculate_risk_score_delta('valid', True, False)
        assert delta == 20.0
        
        # Data change
        delta = _calculate_risk_score_delta('company_name', 'Old', 'New')
        assert delta == 5.0
        
        # No change
        delta = _calculate_risk_score_delta('unknown_field', 'old', 'new')
        assert delta == 0.0
    
    def test_calculate_next_check_time(self, app, counterparty, kyb_config):
        """Test next check time calculation."""
        now = datetime.utcnow()
        
        # Critical risk - daily
        counterparty.risk_level = 'critical'
        next_check = _calculate_next_check_time(counterparty, kyb_config)
        assert next_check > now
        assert next_check <= now + timedelta(days=1, hours=1)
        
        # High risk - use config frequency
        counterparty.risk_level = 'high'
        kyb_config.high_risk_check_frequency = 'weekly'
        next_check = _calculate_next_check_time(counterparty, kyb_config)
        assert next_check > now + timedelta(days=6)
        
        # Low risk - use config frequency
        counterparty.risk_level = 'low'
        kyb_config.low_risk_check_frequency = 'monthly'
        next_check = _calculate_next_check_time(counterparty, kyb_config)
        assert next_check > now + timedelta(days=29)
    
    def test_compare_snapshots(self, app, counterparty):
        """Test snapshot comparison."""
        # Create old snapshot
        old_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='old_hash',
            raw_data={'status': 'valid'},
            processed_data={
                'valid': True,
                'company_name': 'Old Company Name',
                'address': 'Old Address'
            },
            status='valid'
        )
        
        # Create new snapshot with changes
        new_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='new_hash',
            raw_data={'status': 'valid'},
            processed_data={
                'valid': True,
                'company_name': 'New Company Name',
                'phone': '+49123456789'  # New field
            },
            status='valid'
        )
        
        changes = _compare_snapshots(old_snapshot, new_snapshot)
        
        # Should detect 3 changes: company_name modified, phone added, address removed
        assert len(changes) == 3
        
        # Check company name change
        name_change = next(c for c in changes if c['field_path'] == 'company_name')
        assert name_change['change_type'] == 'modified'
        assert name_change['old_value'] == 'Old Company Name'
        assert name_change['new_value'] == 'New Company Name'
        
        # Check phone addition
        phone_change = next(c for c in changes if c['field_path'] == 'phone')
        assert phone_change['change_type'] == 'added'
        assert phone_change['old_value'] is None
        assert phone_change['new_value'] == '+49123456789'
        
        # Check address removal
        address_change = next(c for c in changes if c['field_path'] == 'address')
        assert address_change['change_type'] == 'removed'
        assert address_change['old_value'] == 'Old Address'
        assert address_change['new_value'] is None
    
    def test_update_counterparty_risk_score(self, app, counterparty):
        """Test risk score update."""
        # Create snapshots with different risk factors
        
        # Sanctions match snapshot
        sanctions_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='SANCTIONS_EU',
            check_type='sanctions_eu',
            data_hash='sanctions_hash',
            raw_data={'matches': [{'name': 'Test Company'}]},
            processed_data={
                'matches_found': True,
                'match_count': 1
            },
            status='valid'
        )
        db.session.add(sanctions_snapshot)
        
        # Invalid VAT snapshot
        vat_snapshot = CounterpartySnapshot(
            tenant_id=counterparty.tenant_id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='vat_hash',
            raw_data={'status': 'invalid'},
            processed_data={'valid': False},
            status='invalid'
        )
        db.session.add(vat_snapshot)
        db.session.commit()
        
        # Update risk score
        _update_counterparty_risk_score(counterparty)
        
        # Should have high risk score (70 for sanctions + 20 for invalid VAT)
        assert counterparty.risk_score == 90.0
        assert counterparty.risk_level == 'critical'


if __name__ == '__main__':
    pytest.main([__file__])