"""Simple tests for KYB monitoring models without full app context."""
import pytest
from datetime import datetime
from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch

# Mock the schema function to return None for SQLite tests
with patch('app.utils.schema.get_schema_name', return_value=None):
    from app.models.kyb_monitoring import (
        Counterparty, CounterpartySnapshot, CounterpartyDiff, 
        KYBAlert, KYBMonitoringConfig
    )


@pytest.fixture
def db_session():
    """Create in-memory SQLite database for testing."""
    engine = create_engine('sqlite:///:memory:', echo=False)
    
    # Create metadata and all tables
    metadata = MetaData()
    
    # Create tables manually for testing
    from sqlalchemy import Table, Column, Integer, String, Text, Boolean, DateTime, Float
    from sqlalchemy.dialects.postgresql import JSONB
    from sqlalchemy.sql import func
    
    # Use JSON instead of JSONB for SQLite
    JSON = String  # SQLite doesn't have native JSON, use String
    
    counterparties = Table('counterparties', metadata,
        Column('id', Integer, primary_key=True),
        Column('tenant_id', Integer, nullable=False),
        Column('name', String(255), nullable=False),
        Column('vat_number', String(50)),
        Column('lei_code', String(20)),
        Column('country_code', String(2)),
        Column('email', String(255)),
        Column('risk_score', Float, default=0.0),
        Column('risk_level', String(20), default='low'),
        Column('status', String(50), default='active'),
        Column('monitoring_enabled', Boolean, default=True),
        Column('deleted_at', DateTime),
        Column('created_at', DateTime, default=func.now()),
        Column('updated_at', DateTime, default=func.now())
    )
    
    counterparty_snapshots = Table('counterparty_snapshots', metadata,
        Column('id', Integer, primary_key=True),
        Column('tenant_id', Integer, nullable=False),
        Column('counterparty_id', Integer, nullable=False),
        Column('source', String(100), nullable=False),
        Column('check_type', String(50), nullable=False),
        Column('data_hash', String(64), nullable=False),
        Column('raw_data', JSON, nullable=False),
        Column('status', String(50), nullable=False),
        Column('response_time_ms', Integer),
        Column('error_message', Text),
        Column('created_at', DateTime, default=func.now()),
        Column('updated_at', DateTime, default=func.now())
    )
    
    kyb_alerts = Table('kyb_alerts', metadata,
        Column('id', Integer, primary_key=True),
        Column('tenant_id', Integer, nullable=False),
        Column('counterparty_id', Integer, nullable=False),
        Column('alert_type', String(50), nullable=False),
        Column('severity', String(20), nullable=False),
        Column('title', String(255), nullable=False),
        Column('message', Text, nullable=False),
        Column('status', String(50), default='open'),
        Column('acknowledged_at', DateTime),
        Column('acknowledged_by_id', Integer),
        Column('resolved_at', DateTime),
        Column('resolved_by_id', Integer),
        Column('resolution_notes', Text),
        Column('notification_sent', Boolean, default=False),
        Column('alert_data', JSON),
        Column('source', String(100)),
        Column('created_at', DateTime, default=func.now()),
        Column('updated_at', DateTime, default=func.now())
    )
    
    kyb_monitoring_configs = Table('kyb_monitoring_configs', metadata,
        Column('id', Integer, primary_key=True),
        Column('tenant_id', Integer, nullable=False),
        Column('vies_enabled', Boolean, default=True),
        Column('gleif_enabled', Boolean, default=True),
        Column('sanctions_eu_enabled', Boolean, default=True),
        Column('sanctions_ofac_enabled', Boolean, default=True),
        Column('sanctions_uk_enabled', Boolean, default=True),
        Column('insolvency_de_enabled', Boolean, default=False),
        Column('default_check_frequency', String(20), default='daily'),
        Column('alert_on_sanctions_match', Boolean, default=True),
        Column('email_notifications', Boolean, default=True),
        Column('sanctions_weight', Float, default=100.0),
        Column('snapshot_retention_days', Integer, default=365),
        Column('alert_retention_days', Integer, default=1095),
        Column('created_at', DateTime, default=func.now()),
        Column('updated_at', DateTime, default=func.now())
    )
    
    metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()


class TestCounterpartyModel:
    """Test Counterparty model basic functionality."""
    
    def test_counterparty_creation(self, db_session):
        """Test creating a counterparty."""
        counterparty = Counterparty(
            tenant_id=1,
            name="Test Company Ltd",
            vat_number="GB123456789",
            lei_code="213800ABCDEFGHIJKLMN01",
            country_code="GB",
            email="contact@testcompany.com"
        )
        
        db_session.add(counterparty)
        db_session.commit()
        
        assert counterparty.id is not None
        assert counterparty.name == "Test Company Ltd"
        assert counterparty.vat_number == "GB123456789"
        assert counterparty.risk_level == "low"
        assert counterparty.status == "active"
        assert counterparty.monitoring_enabled is True
    
    def test_counterparty_risk_level_update(self, db_session):
        """Test risk level update based on risk score."""
        counterparty = Counterparty(
            tenant_id=1,
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
    
    def test_counterparty_soft_delete(self, db_session):
        """Test soft delete functionality."""
        counterparty = Counterparty(
            tenant_id=1,
            name="To Be Deleted"
        )
        
        db_session.add(counterparty)
        db_session.commit()
        
        assert counterparty.is_deleted is False
        
        counterparty.soft_delete()
        db_session.commit()
        
        assert counterparty.is_deleted is True
        assert counterparty.deleted_at is not None
        
        counterparty.restore()
        db_session.commit()
        
        assert counterparty.is_deleted is False
        assert counterparty.deleted_at is None


class TestCounterpartySnapshot:
    """Test CounterpartySnapshot model."""
    
    def test_snapshot_creation(self, db_session):
        """Test creating a counterparty snapshot."""
        # First create a counterparty
        counterparty = Counterparty(
            tenant_id=1,
            name="Test Company"
        )
        db_session.add(counterparty)
        db_session.commit()
        
        snapshot = CounterpartySnapshot(
            tenant_id=1,
            counterparty_id=counterparty.id,
            source="VIES",
            check_type="vat",
            data_hash="abc123def456",
            raw_data={"valid": True, "name": "Test Company Ltd"},
            status="valid",
            response_time_ms=250
        )
        
        db_session.add(snapshot)
        db_session.commit()
        
        assert snapshot.id is not None
        assert snapshot.source == "VIES"
        assert snapshot.check_type == "vat"
        assert snapshot.status == "valid"
        assert snapshot.raw_data["valid"] is True
        assert snapshot.response_time_ms == 250
    
    def test_snapshot_with_error(self, db_session):
        """Test creating a snapshot with error status."""
        counterparty = Counterparty(
            tenant_id=1,
            name="Test Company"
        )
        db_session.add(counterparty)
        db_session.commit()
        
        snapshot = CounterpartySnapshot(
            tenant_id=1,
            counterparty_id=counterparty.id,
            source="GLEIF",
            check_type="lei",
            data_hash="error123",
            raw_data={},
            status="error",
            error_message="API timeout"
        )
        
        db_session.add(snapshot)
        db_session.commit()
        
        assert snapshot.status == "error"
        assert snapshot.error_message == "API timeout"


class TestKYBAlert:
    """Test KYBAlert model."""
    
    def test_alert_creation(self, db_session):
        """Test creating a KYB alert."""
        counterparty = Counterparty(
            tenant_id=1,
            name="Test Company"
        )
        db_session.add(counterparty)
        db_session.commit()
        
        alert = KYBAlert(
            tenant_id=1,
            counterparty_id=counterparty.id,
            alert_type="sanctions_match",
            severity="high",
            title="Sanctions Match Detected",
            message="Counterparty matches OFAC sanctions list",
            source="OFAC_API",
            alert_data={"match_score": 95, "list": "SDN"}
        )
        
        db_session.add(alert)
        db_session.commit()
        
        assert alert.id is not None
        assert alert.alert_type == "sanctions_match"
        assert alert.severity == "high"
        assert alert.status == "open"
        assert alert.notification_sent is False
        assert alert.alert_data["match_score"] == 95
    
    def test_alert_acknowledge(self, db_session):
        """Test acknowledging an alert."""
        counterparty = Counterparty(
            tenant_id=1,
            name="Test Company"
        )
        db_session.add(counterparty)
        db_session.commit()
        
        alert = KYBAlert(
            tenant_id=1,
            counterparty_id=counterparty.id,
            alert_type="data_change",
            severity="medium",
            title="Data Change Detected",
            message="Company address has changed"
        )
        
        db_session.add(alert)
        db_session.commit()
        
        alert.acknowledge(1, "Investigating the change")
        db_session.commit()
        
        assert alert.status == "acknowledged"
        assert alert.acknowledged_by_id == 1
        assert alert.acknowledged_at is not None
        assert alert.resolution_notes == "Investigating the change"
    
    def test_alert_resolve(self, db_session):
        """Test resolving an alert."""
        counterparty = Counterparty(
            tenant_id=1,
            name="Test Company"
        )
        db_session.add(counterparty)
        db_session.commit()
        
        alert = KYBAlert(
            tenant_id=1,
            counterparty_id=counterparty.id,
            alert_type="validation_failure",
            severity="low",
            title="VAT Validation Failed",
            message="VAT number could not be validated"
        )
        
        db_session.add(alert)
        db_session.commit()
        
        alert.resolve(1, "VAT number corrected")
        db_session.commit()
        
        assert alert.status == "resolved"
        assert alert.resolved_by_id == 1
        assert alert.resolved_at is not None
        assert alert.resolution_notes == "VAT number corrected"


class TestKYBMonitoringConfig:
    """Test KYBMonitoringConfig model."""
    
    def test_config_creation(self, db_session):
        """Test creating KYB monitoring configuration."""
        config = KYBMonitoringConfig(
            tenant_id=1,
            vies_enabled=True,
            gleif_enabled=True,
            sanctions_eu_enabled=True,
            default_check_frequency="daily",
            alert_on_sanctions_match=True,
            email_notifications=True,
            sanctions_weight=100.0,
            snapshot_retention_days=365
        )
        
        db_session.add(config)
        db_session.commit()
        
        assert config.id is not None
        assert config.vies_enabled is True
        assert config.default_check_frequency == "daily"
        assert config.sanctions_weight == 100.0
        assert config.snapshot_retention_days == 365
    
    def test_config_defaults(self, db_session):
        """Test default values for monitoring configuration."""
        config = KYBMonitoringConfig(tenant_id=1)
        
        db_session.add(config)
        db_session.commit()
        
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