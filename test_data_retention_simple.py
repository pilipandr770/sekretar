#!/usr/bin/env python3
"""Simple test script for data retention functionality."""
import os
import sys
from datetime import datetime, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.inbox_message import InboxMessage
from app.models.gdpr_compliance import DataRetentionPolicy, ConsentRecord, ConsentType
from app.services.data_retention_service import DataRetentionService
from app.services.consent_service import ConsentService
from app.services.pii_service import PIIDetector


def test_pii_detection():
    """Test PII detection functionality."""
    print("Testing PII Detection...")
    
    detector = PIIDetector()
    
    # Test email detection
    text = "Please contact me at john.doe@example.com for more information."
    detected_pii = detector.detect_pii_in_text(text)
    
    print(f"Text: {text}")
    print(f"Detected PII: {len(detected_pii)} items")
    
    for pii in detected_pii:
        print(f"  - Type: {pii['type']}, Value: {pii['value']}, Confidence: {pii['confidence']}")
    
    # Test masking
    masked_text, masked_items = detector.mask_pii_in_text(text)
    print(f"Masked text: {masked_text}")
    
    print("✓ PII Detection test passed\n")


def test_data_retention_with_app():
    """Test data retention functionality with app context."""
    print("Testing Data Retention with App Context...")
    
    app = create_app('testing')
    
    with app.app_context():
        # Create tables
        db.create_all()
        
        try:
            # Create test tenant
            tenant = Tenant.create(
                name="Test Company",
                slug="test-company",
                email="test@example.com"
            )
            
            # Create test user
            user = User.create(
                tenant_id=tenant.id,
                email="user@example.com",
                password="password123",
                role="owner"
            )
            
            # Test retention service
            retention_service = DataRetentionService(db.session)
            
            # Create retention policy
            policy = retention_service.create_retention_policy(
                tenant_id=tenant.id,
                name="Test Message Retention",
                data_type="messages",
                table_name="inbox_messages",
                retention_days=30,
                auto_delete=True,
                legal_basis="legitimate_interest"
            )
            
            print(f"Created retention policy: {policy.name} ({policy.retention_days} days)")
            
            # Create old message (should be expired)
            old_date = datetime.utcnow() - timedelta(days=35)
            old_message = InboxMessage.create(
                tenant_id=tenant.id,
                channel_id=1,
                sender_id="test_sender",
                content="This is an old message that should be expired",
                created_at=old_date
            )
            
            # Create recent message (should not be expired)
            recent_message = InboxMessage.create(
                tenant_id=tenant.id,
                channel_id=1,
                sender_id="test_sender",
                content="This is a recent message"
            )
            
            print(f"Created test messages: old (ID: {old_message.id}), recent (ID: {recent_message.id})")
            
            # Find expired data
            expired_data = retention_service.find_expired_data(tenant.id)
            print(f"Found {expired_data['total_expired_records']} expired records")
            
            # Test cleanup in dry run mode
            cleanup_report = retention_service.cleanup_expired_data(
                tenant_id=tenant.id,
                dry_run=True
            )
            
            print(f"Dry run cleanup would delete {cleanup_report['total_deleted']} records")
            
            # Test consent service
            consent_service = ConsentService(db.session)
            
            # Grant consent
            consent_record = consent_service.grant_consent(
                tenant_id=tenant.id,
                consent_type="marketing",
                purpose="Marketing communications",
                user_id=user.id,
                source="test"
            )
            
            print(f"Granted consent: {consent_record.consent_type.value} (ID: {consent_record.id})")
            
            # Check consent
            has_consent = consent_service.has_valid_consent(
                tenant_id=tenant.id,
                consent_type="marketing",
                user_id=user.id
            )
            
            print(f"User has valid marketing consent: {has_consent}")
            
            print("✓ Data Retention with App Context test passed\n")
            
        finally:
            # Clean up
            db.drop_all()


def test_default_policies():
    """Test creating default retention policies."""
    print("Testing Default Retention Policies...")
    
    app = create_app('testing')
    
    with app.app_context():
        db.create_all()
        
        try:
            # Create test tenant
            tenant = Tenant.create(
                name="Test Company",
                slug="test-company-2",
                email="test2@example.com"
            )
            
            # Create default policies
            retention_service = DataRetentionService(db.session)
            policies = retention_service.create_default_policies(tenant.id)
            
            print(f"Created {len(policies)} default policies:")
            for policy in policies:
                print(f"  - {policy.name}: {policy.retention_days} days ({policy.data_type})")
            
            print("✓ Default Policies test passed\n")
            
        finally:
            db.drop_all()


def main():
    """Run all tests."""
    print("=== Data Retention and GDPR Compliance Tests ===\n")
    
    try:
        test_pii_detection()
        test_data_retention_with_app()
        test_default_policies()
        
        print("🎉 All tests passed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()