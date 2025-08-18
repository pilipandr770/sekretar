#!/usr/bin/env python3
"""Test script for notification system."""
import sys
import os
from datetime import datetime

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.models import Tenant, User, NotificationType, NotificationPriority
from app.services.notification_service import NotificationService
from app.services.notification_templates import NotificationTemplateManager
from app.utils.database import db


def test_notification_system():
    """Test the notification system functionality."""
    app = create_app()
    
    with app.app_context():
        print("🔔 Testing Notification System")
        print("=" * 50)
        
        # Create test tenant and user
        tenant = Tenant.query.first()
        if not tenant:
            tenant = Tenant(
                id="test-tenant",
                name="Test Company",
                domain="test.com"
            )
            db.session.add(tenant)
            db.session.commit()
            print(f"✅ Created test tenant: {tenant.name}")
        else:
            print(f"✅ Using existing tenant: {tenant.name}")
        
        user = User.query.filter_by(tenant_id=tenant.id).first()
        if not user:
            user = User(
                id="test-user",
                tenant_id=tenant.id,
                email="test@test.com",
                role="admin"
            )
            db.session.add(user)
            db.session.commit()
            print(f"✅ Created test user: {user.email}")
        else:
            print(f"✅ Using existing user: {user.email}")
        
        # Create notification service
        service = NotificationService()
        
        # Test 1: Create default templates
        print("\n📋 Testing Template Creation")
        print("-" * 30)
        
        templates = NotificationTemplateManager.create_default_templates(tenant.id)
        print(f"✅ Created {len(templates)} default templates")
        
        # List templates
        all_templates = NotificationTemplateManager.list_templates(tenant.id)
        print(f"✅ Total templates available: {len(all_templates)}")
        
        for template in all_templates[:3]:  # Show first 3
            print(f"   - {template.name} ({template.type})")
        
        # Test 2: Set user preferences
        print("\n⚙️  Testing User Preferences")
        print("-" * 30)
        
        # Set email preference for KYB alerts
        email_pref = service.set_user_preference(
            user_id=user.id,
            tenant_id=tenant.id,
            event_type="kyb_alert",
            notification_type=NotificationType.EMAIL,
            delivery_address="test@test.com",
            is_enabled=True
        )
        print(f"✅ Set email preference: {email_pref.event_type} -> {email_pref.notification_type}")
        
        # Set system notification preference
        system_pref = service.set_user_preference(
            user_id=user.id,
            tenant_id=tenant.id,
            event_type="system_notification",
            notification_type=NotificationType.EMAIL,
            delivery_address="test@test.com",
            is_enabled=True
        )
        print(f"✅ Set system preference: {system_pref.event_type} -> {system_pref.notification_type}")
        
        # Test 3: Create direct notification
        print("\n📧 Testing Direct Notification Creation")
        print("-" * 40)
        
        notification = service.create_notification(
            tenant_id=tenant.id,
            recipient="test@test.com",
            notification_type=NotificationType.EMAIL,
            subject="Test Notification",
            body="This is a test notification from the notification system.",
            user_id=user.id,
            priority=NotificationPriority.NORMAL
        )
        print(f"✅ Created notification: {notification.id}")
        print(f"   Subject: {notification.subject}")
        print(f"   Status: {notification.status}")
        
        # Test 4: Test preference-based notifications
        print("\n🎯 Testing Preference-Based Notifications")
        print("-" * 42)
        
        # Send KYB alert
        kyb_data = {
            'company_name': 'Test Company',
            'counterparty_name': 'Test Counterparty',
            'alert_type': 'Sanctions Match',
            'severity': 'High',
            'details': 'Potential sanctions match detected',
            'detected_at': datetime.utcnow().isoformat(),
            'recommendations': [
                'Review counterparty relationship',
                'Consult legal team',
                'Document findings'
            ]
        }
        
        try:
            task_ids = service.send_to_user_preferences(
                user_id=user.id,
                event_type="kyb_alert",
                data=kyb_data,
                priority=NotificationPriority.HIGH
            )
            print(f"✅ Queued KYB alert notification, task IDs: {task_ids}")
        except Exception as e:
            print(f"⚠️  KYB alert queuing failed (Celery not running?): {str(e)}")
        
        # Send system notification
        system_data = {
            'company_name': 'Test Company',
            'title': 'System Maintenance',
            'message': 'Scheduled maintenance will occur tonight from 2-4 AM.',
            'action_required': 'No action required from users',
            'deadline': 'Tonight 2:00 AM'
        }
        
        try:
            task_ids = service.send_to_user_preferences(
                user_id=user.id,
                event_type="system_notification",
                data=system_data,
                priority=NotificationPriority.NORMAL
            )
            print(f"✅ Queued system notification, task IDs: {task_ids}")
        except Exception as e:
            print(f"⚠️  System notification queuing failed (Celery not running?): {str(e)}")
        
        # Test 5: Check notification status
        print("\n📊 Testing Notification Status")
        print("-" * 32)
        
        status = service.get_notification_status(notification.id)
        if status:
            print(f"✅ Retrieved notification status:")
            print(f"   ID: {status['id']}")
            print(f"   Status: {status['status']}")
            print(f"   Type: {status['type']}")
            print(f"   Recipient: {status['recipient']}")
            print(f"   Created: {status['created_at']}")
            print(f"   Events: {len(status['events'])}")
        else:
            print("❌ Failed to retrieve notification status")
        
        # Test 6: Get user preferences
        print("\n👤 Testing User Preference Retrieval")
        print("-" * 37)
        
        preferences = service.get_user_preferences(user.id)
        print(f"✅ Retrieved {len(preferences)} user preferences:")
        
        for pref in preferences:
            status_icon = "🟢" if pref['is_enabled'] else "🔴"
            print(f"   {status_icon} {pref['event_type']} -> {pref['notification_type']} ({pref['delivery_address']})")
        
        # Test 7: Template operations
        print("\n📝 Testing Template Operations")
        print("-" * 31)
        
        # Get specific template
        kyb_template = NotificationTemplateManager.get_template(tenant.id, 'kyb_alert_email')
        if kyb_template:
            print(f"✅ Retrieved KYB email template: {kyb_template.name}")
            print(f"   Variables: {kyb_template.variables}")
            
            # Update template
            updated = NotificationTemplateManager.update_template(
                kyb_template.id,
                subject_template="🚨 UPDATED: {{ alert_type }} for {{ counterparty_name }}"
            )
            print(f"✅ Updated template subject")
        else:
            print("❌ KYB email template not found")
        
        print("\n🎉 Notification System Test Complete!")
        print("=" * 50)
        
        # Summary
        print("\n📋 Summary:")
        print(f"   • Templates created: {len(templates)}")
        print(f"   • User preferences set: {len(preferences)}")
        print(f"   • Direct notifications created: 1")
        print(f"   • Preference-based notifications queued: 2 (if Celery running)")
        
        print("\n💡 Next Steps:")
        print("   • Start Celery worker to process queued notifications")
        print("   • Configure SMTP settings for email delivery")
        print("   • Set up Telegram/Signal channels for multi-channel delivery")
        print("   • Use the API endpoints to manage notifications programmatically")


if __name__ == "__main__":
    test_notification_system()