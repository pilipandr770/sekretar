"""Tests for KYB monitoring endpoints."""
import pytest
import json
from datetime import datetime, timedelta
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, CounterpartyDiff, 
    KYBAlert, KYBMonitoringConfig
)
from app.models.user import User
from app.models.tenant import Tenant


class TestCounterpartyEndpoints:
    """Test counterparty management endpoints."""
    
    def test_list_counterparties_empty(self, client, auth_headers):
        """Test listing counterparties when none exist."""
        response = client.get('/api/v1/kyb/counterparties', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['items'] == []
        assert data['data']['total'] == 0
    
    def test_create_counterparty_success(self, client, auth_headers):
        """Test creating a new counterparty."""
        counterparty_data = {
            'name': 'Test Company Ltd',
            'vat_number': 'GB123456789',
            'lei_code': 'TESTLEI123456789012',
            'country_code': 'GB',
            'email': 'contact@testcompany.com',
            'monitoring_enabled': True
        }
        
        response = client.post(
            '/api/v1/kyb/counterparties',
            headers=auth_headers,
            json=counterparty_data
        )
        assert response.status_code == 201
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['name'] == 'Test Company Ltd'
        assert data['data']['vat_number'] == 'GB123456789'
        assert data['data']['lei_code'] == 'TESTLEI123456789012'
        assert data['data']['monitoring_enabled'] is True
    
    def test_create_counterparty_missing_name(self, client, auth_headers):
        """Test creating counterparty without required name."""
        counterparty_data = {
            'vat_number': 'GB123456789'
        }
        
        response = client.post(
            '/api/v1/kyb/counterparties',
            headers=auth_headers,
            json=counterparty_data
        )
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'name' in data['message'].lower()
    
    def test_create_counterparty_duplicate_vat(self, client, auth_headers, sample_tenant):
        """Test creating counterparty with duplicate VAT number."""
        # Create first counterparty
        Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Existing Company',
            vat_number='GB123456789'
        )
        
        # Try to create second with same VAT
        counterparty_data = {
            'name': 'New Company',
            'vat_number': 'GB123456789'
        }
        
        response = client.post(
            '/api/v1/kyb/counterparties',
            headers=auth_headers,
            json=counterparty_data
        )
        assert response.status_code == 409
        
        data = json.loads(response.data)
        assert data['success'] is False
        assert 'vat number already exists' in data['message'].lower()
    
    def test_get_counterparty_success(self, client, auth_headers, sample_tenant):
        """Test getting a specific counterparty."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company',
            vat_number='GB123456789',
            risk_score=45.5
        )
        
        response = client.get(
            f'/api/v1/kyb/counterparties/{counterparty.id}',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['name'] == 'Test Company'
        assert data['data']['risk_score'] == 45.5
        assert 'recent_snapshots' in data['data']
        assert 'recent_alerts' in data['data']
        assert 'statistics' in data['data']
    
    def test_get_counterparty_not_found(self, client, auth_headers):
        """Test getting non-existent counterparty."""
        response = client.get('/api/v1/kyb/counterparties/999', headers=auth_headers)
        assert response.status_code == 404
        
        data = json.loads(response.data)
        assert data['success'] is False
    
    def test_update_counterparty_success(self, client, auth_headers, sample_tenant):
        """Test updating a counterparty."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Old Name',
            vat_number='GB123456789'
        )
        
        update_data = {
            'name': 'New Name',
            'email': 'new@email.com',
            'monitoring_enabled': False
        }
        
        response = client.put(
            f'/api/v1/kyb/counterparties/{counterparty.id}',
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['name'] == 'New Name'
        assert data['data']['email'] == 'new@email.com'
        assert data['data']['monitoring_enabled'] is False
    
    def test_delete_counterparty_success(self, client, auth_headers, sample_tenant):
        """Test deleting a counterparty."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='To Delete',
            vat_number='GB123456789'
        )
        
        response = client.delete(
            f'/api/v1/kyb/counterparties/{counterparty.id}',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        
        # Verify soft delete
        deleted_cp = Counterparty.query.get(counterparty.id)
        assert deleted_cp.deleted_at is not None
    
    def test_list_counterparties_with_filters(self, client, auth_headers, sample_tenant):
        """Test listing counterparties with various filters."""
        # Create test counterparties
        cp1 = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='High Risk Company',
            risk_level='high',
            country_code='GB',
            monitoring_enabled=True
        )
        cp2 = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Low Risk Company',
            risk_level='low',
            country_code='DE',
            monitoring_enabled=False
        )
        
        # Test risk level filter
        response = client.get(
            '/api/v1/kyb/counterparties?risk_level=high',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['name'] == 'High Risk Company'
        
        # Test country filter
        response = client.get(
            '/api/v1/kyb/counterparties?country_code=DE',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['name'] == 'Low Risk Company'
        
        # Test monitoring enabled filter
        response = client.get(
            '/api/v1/kyb/counterparties?monitoring_enabled=true',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['name'] == 'High Risk Company'
        
        # Test search
        response = client.get(
            '/api/v1/kyb/counterparties?search=High',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['name'] == 'High Risk Company'


class TestKYBConfigEndpoints:
    """Test KYB configuration endpoints."""
    
    def test_get_kyb_config_creates_default(self, client, auth_headers):
        """Test getting KYB config creates default if none exists."""
        response = client.get('/api/v1/kyb/config', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['vies_enabled'] is True
        assert data['data']['gleif_enabled'] is True
        assert data['data']['default_check_frequency'] == 'daily'
    
    def test_update_kyb_config_success(self, client, auth_headers, sample_tenant):
        """Test updating KYB configuration."""
        # Create initial config
        config = KYBMonitoringConfig.create(tenant_id=sample_tenant.id)
        
        update_data = {
            'vies_enabled': False,
            'sanctions_eu_enabled': True,
            'default_check_frequency': 'weekly',
            'email_notifications': False,
            'sanctions_weight': 95.0
        }
        
        response = client.put(
            '/api/v1/kyb/config',
            headers=auth_headers,
            json=update_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['vies_enabled'] is False
        assert data['data']['sanctions_eu_enabled'] is True
        assert data['data']['default_check_frequency'] == 'weekly'
        assert data['data']['email_notifications'] is False
        assert data['data']['sanctions_weight'] == 95.0


class TestKYBAlertEndpoints:
    """Test KYB alert management endpoints."""
    
    def test_list_kyb_alerts_empty(self, client, auth_headers):
        """Test listing KYB alerts when none exist."""
        response = client.get('/api/v1/kyb/alerts', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['items'] == []
        assert data['data']['total'] == 0
    
    def test_list_kyb_alerts_with_data(self, client, auth_headers, sample_tenant, sample_user):
        """Test listing KYB alerts with test data."""
        # Create counterparty and alert
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='sanctions_match',
            severity='high',
            title='Sanctions Match Found',
            message='Company found on sanctions list'
        )
        
        response = client.get('/api/v1/kyb/alerts', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['alert_type'] == 'sanctions_match'
        assert data['data']['items'][0]['severity'] == 'high'
    
    def test_get_kyb_alert_success(self, client, auth_headers, sample_tenant):
        """Test getting a specific KYB alert."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='data_change',
            severity='medium',
            title='Data Change Detected',
            message='VAT status changed'
        )
        
        response = client.get(f'/api/v1/kyb/alerts/{alert.id}', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['alert_type'] == 'data_change'
        assert data['data']['severity'] == 'medium'
    
    def test_acknowledge_kyb_alert_success(self, client, auth_headers, sample_tenant):
        """Test acknowledging a KYB alert."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='vat_invalid',
            severity='low',
            title='VAT Invalid',
            message='VAT number validation failed',
            status='open'
        )
        
        acknowledge_data = {
            'notes': 'Acknowledged by compliance team'
        }
        
        response = client.post(
            f'/api/v1/kyb/alerts/{alert.id}/acknowledge',
            headers=auth_headers,
            json=acknowledge_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'acknowledged'
        assert data['data']['resolution_notes'] == 'Acknowledged by compliance team'
    
    def test_resolve_kyb_alert_success(self, client, auth_headers, sample_tenant):
        """Test resolving a KYB alert."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='lei_invalid',
            severity='medium',
            title='LEI Invalid',
            message='LEI code validation failed',
            status='open'
        )
        
        resolve_data = {
            'notes': 'Issue resolved - LEI updated'
        }
        
        response = client.post(
            f'/api/v1/kyb/alerts/{alert.id}/resolve',
            headers=auth_headers,
            json=resolve_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'resolved'
        assert data['data']['resolution_notes'] == 'Issue resolved - LEI updated'
    
    def test_mark_kyb_alert_false_positive(self, client, auth_headers, sample_tenant):
        """Test marking a KYB alert as false positive."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='sanctions_match',
            severity='critical',
            title='Sanctions Match',
            message='Potential sanctions match detected',
            status='open'
        )
        
        false_positive_data = {
            'notes': 'False positive - different entity with similar name'
        }
        
        response = client.post(
            f'/api/v1/kyb/alerts/{alert.id}/false-positive',
            headers=auth_headers,
            json=false_positive_data
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['status'] == 'false_positive'
        assert data['data']['resolution_notes'] == 'False positive - different entity with similar name'
    
    def test_list_kyb_alerts_with_filters(self, client, auth_headers, sample_tenant):
        """Test listing KYB alerts with various filters."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        # Create alerts with different properties
        alert1 = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='sanctions_match',
            severity='critical',
            title='Critical Alert',
            message='Critical issue',
            status='open'
        )
        
        alert2 = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='data_change',
            severity='low',
            title='Low Priority Alert',
            message='Minor change',
            status='resolved'
        )
        
        # Test severity filter
        response = client.get(
            '/api/v1/kyb/alerts?severity=critical',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['severity'] == 'critical'
        
        # Test status filter
        response = client.get(
            '/api/v1/kyb/alerts?status=open',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['status'] == 'open'
        
        # Test alert type filter
        response = client.get(
            '/api/v1/kyb/alerts?alert_type=data_change',
            headers=auth_headers
        )
        assert response.status_code == 200
        data = json.loads(response.data)
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['alert_type'] == 'data_change'


class TestKYBReportingEndpoints:
    """Test KYB reporting and risk assessment endpoints."""
    
    def test_get_risk_assessment_empty(self, client, auth_headers):
        """Test getting risk assessment with no data."""
        response = client.get('/api/v1/kyb/risk-assessment', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['overview']['total_counterparties'] == 0
        assert data['data']['overview']['total_alerts'] == 0
        assert data['data']['risk_distribution']['low'] == 0
        assert data['data']['top_risk_counterparties'] == []
    
    def test_get_risk_assessment_with_data(self, client, auth_headers, sample_tenant):
        """Test getting risk assessment with test data."""
        # Create counterparties with different risk levels
        cp1 = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='High Risk Co',
            risk_level='high',
            risk_score=85.0
        )
        
        cp2 = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Low Risk Co',
            risk_level='low',
            risk_score=15.0
        )
        
        # Create alerts
        alert1 = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=cp1.id,
            alert_type='sanctions_match',
            severity='high',
            title='High Risk Alert',
            message='High risk detected',
            status='open'
        )
        
        alert2 = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=cp2.id,
            alert_type='data_change',
            severity='low',
            title='Low Risk Alert',
            message='Minor change',
            status='resolved'
        )
        
        response = client.get('/api/v1/kyb/risk-assessment', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['overview']['total_counterparties'] == 2
        assert data['data']['overview']['total_alerts'] == 2
        assert data['data']['overview']['open_alerts'] == 1
        assert data['data']['risk_distribution']['high'] == 1
        assert data['data']['risk_distribution']['low'] == 1
        assert len(data['data']['top_risk_counterparties']) == 2
        assert data['data']['top_risk_counterparties'][0]['name'] == 'High Risk Co'
    
    def test_get_kyb_summary_report(self, client, auth_headers, sample_tenant):
        """Test getting KYB summary report."""
        # Create test data
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        # Create snapshots
        snapshot1 = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='hash1',
            raw_data={'status': 'valid'},
            status='valid'
        )
        
        snapshot2 = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='GLEIF',
            check_type='lei',
            data_hash='hash2',
            raw_data={'status': 'invalid'},
            status='invalid'
        )
        
        # Create alert
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='lei_invalid',
            severity='medium',
            title='LEI Invalid',
            message='LEI validation failed'
        )
        
        response = client.get('/api/v1/kyb/reports/summary', headers=auth_headers)
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert data['data']['activity']['total_checks'] == 2
        assert data['data']['activity']['total_alerts'] == 1
        assert 'VIES' in data['data']['data_sources']
        assert 'GLEIF' in data['data']['data_sources']
        assert data['data']['data_sources']['VIES']['valid'] == 1
        assert data['data']['data_sources']['GLEIF']['invalid'] == 1


class TestKYBSnapshotEndpoints:
    """Test KYB snapshot and diff endpoints."""
    
    def test_list_counterparty_snapshots(self, client, auth_headers, sample_tenant):
        """Test listing snapshots for a counterparty."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        # Create snapshots
        snapshot1 = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='hash1',
            raw_data={'status': 'valid'},
            status='valid'
        )
        
        snapshot2 = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='GLEIF',
            check_type='lei',
            data_hash='hash2',
            raw_data={'status': 'active'},
            status='valid'
        )
        
        response = client.get(
            f'/api/v1/kyb/counterparties/{counterparty.id}/snapshots',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 2
        assert data['data']['items'][0]['source'] in ['VIES', 'GLEIF']
        assert data['data']['items'][0]['counterparty_name'] == 'Test Company'
    
    def test_list_counterparty_diffs(self, client, auth_headers, sample_tenant):
        """Test listing diffs for a counterparty."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        # Create snapshots
        old_snapshot = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='hash1',
            raw_data={'status': 'valid'},
            status='valid'
        )
        
        new_snapshot = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='hash2',
            raw_data={'status': 'invalid'},
            status='invalid'
        )
        
        # Create diff
        diff = CounterpartyDiff.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            old_snapshot_id=old_snapshot.id,
            new_snapshot_id=new_snapshot.id,
            field_path='status',
            old_value='valid',
            new_value='invalid',
            change_type='modified',
            risk_impact='medium'
        )
        
        response = client.get(
            f'/api/v1/kyb/counterparties/{counterparty.id}/diffs',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['field_path'] == 'status'
        assert data['data']['items'][0]['old_value'] == 'valid'
        assert data['data']['items'][0]['new_value'] == 'invalid'
        assert data['data']['items'][0]['counterparty_name'] == 'Test Company'
    
    def test_list_snapshots_with_filters(self, client, auth_headers, sample_tenant):
        """Test listing snapshots with filters."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        # Create snapshots with different sources
        vies_snapshot = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='VIES',
            check_type='vat',
            data_hash='hash1',
            raw_data={'status': 'valid'},
            status='valid'
        )
        
        gleif_snapshot = CounterpartySnapshot.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            source='GLEIF',
            check_type='lei',
            data_hash='hash2',
            raw_data={'status': 'active'},
            status='valid'
        )
        
        # Test source filter
        response = client.get(
            f'/api/v1/kyb/counterparties/{counterparty.id}/snapshots?source=VIES',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['source'] == 'VIES'
        
        # Test check_type filter
        response = client.get(
            f'/api/v1/kyb/counterparties/{counterparty.id}/snapshots?check_type=lei',
            headers=auth_headers
        )
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert data['success'] is True
        assert len(data['data']['items']) == 1
        assert data['data']['items'][0]['check_type'] == 'lei'


class TestKYBPermissions:
    """Test KYB endpoint permissions."""
    
    def test_kyb_endpoints_require_authentication(self, client):
        """Test that KYB endpoints require authentication."""
        endpoints = [
            '/api/v1/kyb/counterparties',
            '/api/v1/kyb/config',
            '/api/v1/kyb/alerts',
            '/api/v1/kyb/risk-assessment'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 401
    
    def test_kyb_view_permission_required(self, client, auth_headers_no_permissions):
        """Test that KYB view permission is required for read operations."""
        endpoints = [
            '/api/v1/kyb/counterparties',
            '/api/v1/kyb/config',
            '/api/v1/kyb/alerts',
            '/api/v1/kyb/risk-assessment'
        ]
        
        for endpoint in endpoints:
            response = client.get(endpoint, headers=auth_headers_no_permissions)
            assert response.status_code == 403
    
    def test_kyb_manage_permission_required(self, client, auth_headers_no_permissions):
        """Test that KYB manage permission is required for write operations."""
        endpoints_and_methods = [
            ('/api/v1/kyb/counterparties', 'POST', {'name': 'Test'}),
            ('/api/v1/kyb/counterparties/1', 'PUT', {'name': 'Updated'}),
            ('/api/v1/kyb/counterparties/1', 'DELETE', None),
            ('/api/v1/kyb/config', 'PUT', {'vies_enabled': True}),
            ('/api/v1/kyb/alerts/1/acknowledge', 'POST', {}),
            ('/api/v1/kyb/alerts/1/resolve', 'POST', {}),
            ('/api/v1/kyb/alerts/1/false-positive', 'POST', {})
        ]
        
        for endpoint, method, data in endpoints_and_methods:
            if method == 'POST':
                response = client.post(endpoint, headers=auth_headers_no_permissions, json=data)
            elif method == 'PUT':
                response = client.put(endpoint, headers=auth_headers_no_permissions, json=data)
            elif method == 'DELETE':
                response = client.delete(endpoint, headers=auth_headers_no_permissions)
            
            assert response.status_code == 403


class TestKYBValidation:
    """Test KYB endpoint validation."""
    
    def test_create_counterparty_validation(self, client, auth_headers):
        """Test counterparty creation validation."""
        # Test empty name
        response = client.post(
            '/api/v1/kyb/counterparties',
            headers=auth_headers,
            json={'name': ''}
        )
        assert response.status_code == 400
        
        # Test missing JSON
        response = client.post(
            '/api/v1/kyb/counterparties',
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Test invalid JSON
        response = client.post(
            '/api/v1/kyb/counterparties',
            headers=auth_headers,
            data='invalid json'
        )
        assert response.status_code == 400
    
    def test_pagination_validation(self, client, auth_headers):
        """Test pagination parameter validation."""
        # Test invalid page number
        response = client.get(
            '/api/v1/kyb/counterparties?page=0',
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Test invalid per_page
        response = client.get(
            '/api/v1/kyb/counterparties?per_page=101',
            headers=auth_headers
        )
        assert response.status_code == 400
        
        # Test non-numeric pagination
        response = client.get(
            '/api/v1/kyb/counterparties?page=abc',
            headers=auth_headers
        )
        assert response.status_code == 400
    
    def test_alert_status_validation(self, client, auth_headers, sample_tenant):
        """Test alert status change validation."""
        counterparty = Counterparty.create(
            tenant_id=sample_tenant.id,
            name='Test Company'
        )
        
        # Create resolved alert
        alert = KYBAlert.create(
            tenant_id=sample_tenant.id,
            counterparty_id=counterparty.id,
            alert_type='data_change',
            severity='low',
            title='Test Alert',
            message='Test message',
            status='resolved'
        )
        
        # Try to acknowledge resolved alert
        response = client.post(
            f'/api/v1/kyb/alerts/{alert.id}/acknowledge',
            headers=auth_headers,
            json={'notes': 'Test'}
        )
        assert response.status_code == 400
        
        data = json.loads(response.data)
        assert 'only open alerts' in data['message'].lower()