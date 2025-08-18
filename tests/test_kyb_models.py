"""Tests for KYB monitoring models."""
import pytest
from datetime import datetime, timedelta
from app.models.kyb_monitoring import (
    Counterparty, CounterpartySnapshot, CounterpartyDiff, 
    KYBAlert, KYBMonitoringConfig
)
from app.models.tenant import Tenant
from app.models.user import User
from app import db


class TestCounterparty:
    """Test Counterparty model."""
    
    def test_create_counterparty(self, app, tenant):
        """Test creating a counterparty."""
        with app.app_context():
            counterparty = Counterparty(
                tenant_id=tenant.id,
                name="Test Company Ltd",
                vat_number="GB123456789",
                lei_code="213800ABCDEFGHIJKLMN01",
                country_code="GB",
                email="contact@testcompany.com"
            )
            db.session.add(counterparty)
            db.session.commit()
            
            assert counterparty.id is not None
            assert counterparty.name == "Test Company Ltd"
            assert counterparty.vat_number == "GB123456789"
            assert counterparty.risk_level == "low"
            assert counterparty.status == "active"
            assert counterparty.monitoring_enabled is True
    
    def test_counterparty_risk_level_update(self, app, tenant):
        """Test risk level update based on risk score."""
        with app.app_context():
            counterparty = Counterparty(
                tenant_id=tenant.id,
                name="High Risk Company",
                risk_score=95.0
            )
            counterparty.update_risk_level()
            
            assert counterparty.risk_level == "critical"
            
            counterparty.risk_score = 75.0
            counterparty.update_risk_level()
            assert counterparty.risk_level == "high"
            
            counterparty.risk_score = 50.0
            counterparty.update_risk_level()
            assert counterparty.risk_level == "medium"
            
            counterparty.risk_score = 20.0
            counterparty.update_risk_level()
            assert counterparty.risk_level == "low"
    
    def test_counterparty_soft_delete(self, app, tenant):
        """Test soft delete functionality."""
        with app.app_context():
            counterparty = Counterparty(
                tenant_id=tenant.id,
                name="To Be Deleted"
            )
            db.session.add(counterparty)
            db.session.commit()
            
            assert counterparty.is_deleted is False
            
            counterparty.soft_delete()
            db.session.commit()
            
            assert counterparty.is_deleted is True
            assert counterparty.deleted_at is not None
            
            counterparty.restore()
            db.session.commit()
            
            assert counterparty.is_deleted is False
            assert counterparty.deleted_at is None


class TestCounterpartySnapshot:
    """Test CounterpartySnapshot model."""
    
    def test_create_snapshot(self, app, tenant, counterparty):
        """Test creating a counterparty snapshot."""
        with app.app_context():
            snapshot = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="VIES",
                check_type="vat",
                data_hash="abc123def456",
                raw_data={"valid": True, "name": "Test Company Ltd"},
                status="valid",
                response_time_ms=250
            )
            db.session.add(snapshot)
            db.session.commit()
            
            assert snapshot.id is not None
            assert snapshot.source == "VIES"
            assert snapshot.check_type == "vat"
            assert snapshot.status == "valid"
            assert snapshot.raw_data["valid"] is True
            assert snapshot.response_time_ms == 250
    
    def test_snapshot_with_error(self, app, tenant, counterparty):
        """Test creating a snapshot with error status."""
        with app.app_context():
            snapshot = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="GLEIF",
                check_type="lei",
                data_hash="error123",
                raw_data={},
                status="error",
                error_message="API timeout"
            )
            db.session.add(snapshot)
            db.session.commit()
            
            assert snapshot.status == "error"
            assert snapshot.error_message == "API timeout"


class TestCounterpartyDiff:
    """Test CounterpartyDiff model."""
    
    def test_create_diff(self, app, tenant, counterparty):
        """Test creating a counterparty diff."""
        with app.app_context():
            # Create old and new snapshots
            old_snapshot = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="VIES",
                check_type="vat",
                data_hash="old123",
                raw_data={"name": "Old Company Name"},
                status="valid"
            )
            new_snapshot = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="VIES",
                check_type="vat",
                data_hash="new456",
                raw_data={"name": "New Company Name"},
                status="valid"
            )
            db.session.add_all([old_snapshot, new_snapshot])
            db.session.commit()
            
            diff = CounterpartyDiff(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                old_snapshot_id=old_snapshot.id,
                new_snapshot_id=new_snapshot.id,
                field_path="name",
                old_value="Old Company Name",
                new_value="New Company Name",
                change_type="modified",
                risk_impact="medium",
                risk_score_delta=10.0
            )
            db.session.add(diff)
            db.session.commit()
            
            assert diff.id is not None
            assert diff.field_path == "name"
            assert diff.change_type == "modified"
            assert diff.risk_impact == "medium"
            assert diff.risk_score_delta == 10.0
            assert diff.processed is False
            assert diff.alert_generated is False


class TestKYBAlert:
    """Test KYBAlert model."""
    
    def test_create_alert(self, app, tenant, counterparty, user):
        """Test creating a KYB alert."""
        with app.app_context():
            alert = KYBAlert(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                alert_type="sanctions_match",
                severity="high",
                title="Sanctions Match Detected",
                message="Counterparty matches OFAC sanctions list",
                source="OFAC_API",
                alert_data={"match_score": 95, "list": "SDN"}
            )
            db.session.add(alert)
            db.session.commit()
            
            assert alert.id is not None
            assert alert.alert_type == "sanctions_match"
            assert alert.severity == "high"
            assert alert.status == "open"
            assert alert.notification_sent is False
            assert alert.alert_data["match_score"] == 95
    
    def test_alert_acknowledge(self, app, tenant, counterparty, user):
        """Test acknowledging an alert."""
        with app.app_context():
            alert = KYBAlert(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                alert_type="data_change",
                severity="medium",
                title="Data Change Detected",
                message="Company address has changed"
            )
            db.session.add(alert)
            db.session.commit()
            
            alert.acknowledge(user.id, "Investigating the change")
            db.session.commit()
            
            assert alert.status == "acknowledged"
            assert alert.acknowledged_by_id == user.id
            assert alert.acknowledged_at is not None
            assert alert.resolution_notes == "Investigating the change"
    
    def test_alert_resolve(self, app, tenant, counterparty, user):
        """Test resolving an alert."""
        with app.app_context():
            alert = KYBAlert(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                alert_type="validation_failure",
                severity="low",
                title="VAT Validation Failed",
                message="VAT number could not be validated"
            )
            db.session.add(alert)
            db.session.commit()
            
            alert.resolve(user.id, "VAT number corrected")
            db.session.commit()
            
            assert alert.status == "resolved"
            assert alert.resolved_by_id == user.id
            assert alert.resolved_at is not None
            assert alert.resolution_notes == "VAT number corrected"
    
    def test_alert_false_positive(self, app, tenant, counterparty, user):
        """Test marking alert as false positive."""
        with app.app_context():
            alert = KYBAlert(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                alert_type="sanctions_match",
                severity="high",
                title="Potential Sanctions Match",
                message="Similar name found in sanctions list"
            )
            db.session.add(alert)
            db.session.commit()
            
            alert.mark_false_positive(user.id, "Different entity confirmed")
            db.session.commit()
            
            assert alert.status == "false_positive"
            assert alert.resolved_by_id == user.id
            assert alert.resolved_at is not None
            assert alert.resolution_notes == "Different entity confirmed"


class TestKYBMonitoringConfig:
    """Test KYBMonitoringConfig model."""
    
    def test_create_config(self, app, tenant):
        """Test creating KYB monitoring configuration."""
        with app.app_context():
            config = KYBMonitoringConfig(
                tenant_id=tenant.id,
                vies_enabled=True,
                gleif_enabled=True,
                sanctions_eu_enabled=True,
                default_check_frequency="daily",
                alert_on_sanctions_match=True,
                email_notifications=True,
                sanctions_weight=100.0,
                snapshot_retention_days=365
            )
            db.session.add(config)
            db.session.commit()
            
            assert config.id is not None
            assert config.vies_enabled is True
            assert config.default_check_frequency == "daily"
            assert config.sanctions_weight == 100.0
            assert config.snapshot_retention_days == 365
    
    def test_config_defaults(self, app, tenant):
        """Test default values for monitoring configuration."""
        with app.app_context():
            config = KYBMonitoringConfig(tenant_id=tenant.id)
            db.session.add(config)
            db.session.commit()
            
            assert config.vies_enabled is True
            assert config.gleif_enabled is True
            assert config.sanctions_eu_enabled is True
            assert config.sanctions_ofac_enabled is True
            assert config.sanctions_uk_enabled is True
            assert config.insolvency_de_enabled is False
            assert config.default_check_frequency == "daily"
            assert config.alert_on_sanctions_match is True
            assert config.email_notifications is True
            assert config.sanctions_weight == 100.0
            assert config.snapshot_retention_days == 365
            assert config.alert_retention_days == 1095


class TestKYBRelationships:
    """Test relationships between KYB models."""
    
    def test_counterparty_snapshots_relationship(self, app, tenant, counterparty):
        """Test counterparty to snapshots relationship."""
        with app.app_context():
            snapshot1 = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="VIES",
                check_type="vat",
                data_hash="hash1",
                raw_data={"valid": True},
                status="valid"
            )
            snapshot2 = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="GLEIF",
                check_type="lei",
                data_hash="hash2",
                raw_data={"valid": False},
                status="invalid"
            )
            db.session.add_all([snapshot1, snapshot2])
            db.session.commit()
            
            # Refresh counterparty to load relationships
            db.session.refresh(counterparty)
            
            assert len(counterparty.snapshots) == 2
            assert snapshot1 in counterparty.snapshots
            assert snapshot2 in counterparty.snapshots
    
    def test_counterparty_alerts_relationship(self, app, tenant, counterparty):
        """Test counterparty to alerts relationship."""
        with app.app_context():
            alert1 = KYBAlert(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                alert_type="sanctions_match",
                severity="high",
                title="Alert 1",
                message="Test alert 1"
            )
            alert2 = KYBAlert(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                alert_type="data_change",
                severity="medium",
                title="Alert 2",
                message="Test alert 2"
            )
            db.session.add_all([alert1, alert2])
            db.session.commit()
            
            # Refresh counterparty to load relationships
            db.session.refresh(counterparty)
            
            assert len(counterparty.alerts) == 2
            assert alert1 in counterparty.alerts
            assert alert2 in counterparty.alerts
    
    def test_diff_snapshots_relationship(self, app, tenant, counterparty):
        """Test diff to snapshots relationship."""
        with app.app_context():
            old_snapshot = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="VIES",
                check_type="vat",
                data_hash="old",
                raw_data={"name": "Old Name"},
                status="valid"
            )
            new_snapshot = CounterpartySnapshot(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                source="VIES",
                check_type="vat",
                data_hash="new",
                raw_data={"name": "New Name"},
                status="valid"
            )
            db.session.add_all([old_snapshot, new_snapshot])
            db.session.commit()
            
            diff = CounterpartyDiff(
                tenant_id=tenant.id,
                counterparty_id=counterparty.id,
                old_snapshot_id=old_snapshot.id,
                new_snapshot_id=new_snapshot.id,
                field_path="name",
                old_value="Old Name",
                new_value="New Name",
                change_type="modified"
            )
            db.session.add(diff)
            db.session.commit()
            
            assert diff.old_snapshot == old_snapshot
            assert diff.new_snapshot == new_snapshot
            assert diff.counterparty == counterparty