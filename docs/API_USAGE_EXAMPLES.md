# AI Secretary SaaS API Usage Examples

This document provides comprehensive examples for integrating with the AI Secretary SaaS API across all major functionality areas.

## Table of Contents

1. [Authentication Examples](#authentication-examples)
2. [Tenant Management](#tenant-management)
3. [Inbox and Communication](#inbox-and-communication)
4. [CRM Operations](#crm-operations)
5. [Calendar Integration](#calendar-integration)
6. [Knowledge Management](#knowledge-management)
7. [Billing and Subscriptions](#billing-and-subscriptions)
8. [KYB Monitoring](#kyb-monitoring)
9. [Channel Management](#channel-management)
10. [Notifications](#notifications)
11. [GDPR Compliance](#gdpr-compliance)
12. [Monitoring and Analytics](#monitoring-and-analytics)

## Authentication Examples

### Register New Tenant

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@newcompany.com",
    "password": "SecurePassword123!",
    "organization_name": "New Company Ltd",
    "first_name": "John",
    "last_name": "Owner",
    "language": "en"
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Registration successful",
  "data": {
    "user": {
      "id": 123,
      "email": "owner@newcompany.com",
      "first_name": "John",
      "last_name": "Owner",
      "role": "owner",
      "is_active": true,
      "language": "en"
    },
    "tenant": {
      "id": 456,
      "name": "New Company Ltd",
      "subscription_status": "trial",
      "trial_ends_at": "2025-08-19T12:00:00Z"
    },
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "Bearer"
  }
}
```

### Login and Get Tokens

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@company.com",
    "password": "UserPassword123!"
  }'
```

### Refresh Access Token

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/auth/refresh" \
  -H "Authorization: Bearer <refresh-token>" \
  -H "Content-Type: application/json"
```

### Get Current User Profile

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/auth/me" \
  -H "Authorization: Bearer <access-token>"
```

## Tenant Management

### Get Tenant Information

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/tenant" \
  -H "Authorization: Bearer <access-token>"
```

### Update Tenant Settings

```bash
curl -X PUT "https://api.ai-secretary.com/api/v1/tenant/settings" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "settings": {
      "ai_response_enabled": true,
      "auto_lead_creation": true,
      "default_language": "en",
      "business_hours": {
        "monday": {"start": "09:00", "end": "17:00"},
        "tuesday": {"start": "09:00", "end": "17:00"},
        "wednesday": {"start": "09:00", "end": "17:00"},
        "thursday": {"start": "09:00", "end": "17:00"},
        "friday": {"start": "09:00", "end": "17:00"},
        "saturday": null,
        "sunday": null
      },
      "notification_preferences": {
        "email_notifications": true,
        "telegram_notifications": true,
        "new_lead_alerts": true,
        "kyb_alerts": true
      }
    }
  }'
```

### Create New User

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/tenant/users" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@company.com",
    "role": "support",
    "first_name": "Jane",
    "last_name": "Support",
    "language": "en",
    "is_active": true
  }'
```

### List Tenant Users

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/tenant/users?page=1&per_page=20&role=support&is_active=true" \
  -H "Authorization: Bearer <access-token>"
```

## Inbox and Communication

### List Messages with Filters

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/inbox/messages?channel=telegram&status=new&page=1&per_page=20" \
  -H "Authorization: Bearer <access-token>"
```

### Create New Message

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/inbox/messages" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Customer inquiry about our AI secretary services",
    "channel": "web_widget",
    "customer_email": "prospect@example.com",
    "customer_name": "John Prospect",
    "metadata": {
      "source_url": "https://company.com/contact",
      "user_agent": "Mozilla/5.0...",
      "ip_address": "192.168.1.100"
    }
  }'
```

### Update Message Status

```bash
curl -X PUT "https://api.ai-secretary.com/api/v1/inbox/messages/123" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved",
    "ai_response": "Thank you for your inquiry. We have sent you detailed information about our AI secretary services.",
    "assigned_to": 456
  }'
```

### Search Messages

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/inbox/messages?search=pricing&start_date=2025-08-01&end_date=2025-08-16" \
  -H "Authorization: Bearer <access-token>"
```

## CRM Operations

### List Leads with Advanced Filtering

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/crm/leads?status=qualified&source=website&assigned_to=123&value_min=5000&page=1&per_page=20" \
  -H "Authorization: Bearer <access-token>"
```

### Create New Lead

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/crm/leads" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "contact": {
      "name": "Sarah Johnson",
      "email": "sarah@techcorp.com",
      "phone": "+1-555-0123",
      "company": "TechCorp Solutions"
    },
    "source": "referral",
    "value": 25000,
    "pipeline_id": 1,
    "stage_id": 2,
    "assigned_to": 123,
    "notes": "Referred by existing client. Interested in Enterprise plan.",
    "tags": ["enterprise", "referral", "high-value"],
    "custom_fields": {
      "industry": "Technology",
      "company_size": "50-100",
      "decision_maker": true
    }
  }'
```

### Update Lead Status and Move Through Pipeline

```bash
curl -X PUT "https://api.ai-secretary.com/api/v1/crm/leads/456" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "proposal",
    "stage_id": 3,
    "value": 30000,
    "notes": "Proposal sent. Follow up scheduled for next week."
  }'
```

### Create Task for Lead

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/crm/tasks" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Follow up on proposal",
    "description": "Call Sarah to discuss the proposal and answer any questions",
    "lead_id": 456,
    "assigned_to_id": 123,
    "priority": "high",
    "task_type": "call",
    "category": "sales",
    "due_date": "2025-08-20T10:00:00Z",
    "tags": ["follow-up", "proposal"]
  }'
```

### Add Note to Lead

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/crm/notes" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Discovery Call Notes",
    "content": "Had a great discovery call with Sarah. Key points:\n- Current using manual processes\n- Team of 15 people\n- Looking to automate customer support\n- Budget approved for Q4\n- Decision timeline: 2 weeks",
    "lead_id": 456,
    "note_type": "call",
    "is_private": false,
    "is_pinned": true,
    "tags": ["discovery", "budget-approved"]
  }'
```

### Get Lead with Full Details

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/crm/leads/456?include=tasks,notes,history" \
  -H "Authorization: Bearer <access-token>"
```

## Calendar Integration

### Check Calendar Connection Status

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/calendar/connection/status" \
  -H "Authorization: Bearer <access-token>"
```

### Get Available Time Slots

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/calendar/availability?date=2025-08-20&duration=60&timezone=America/New_York" \
  -H "Authorization: Bearer <access-token>"
```

### Create Calendar Event

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/calendar/events" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product Demo - TechCorp Solutions",
    "description": "Demo call with Sarah Johnson to showcase AI secretary features",
    "start_time": "2025-08-20T14:00:00Z",
    "end_time": "2025-08-20T15:00:00Z",
    "attendees": [
      {
        "email": "sarah@techcorp.com",
        "name": "Sarah Johnson"
      }
    ],
    "lead_id": 456,
    "location": "Google Meet",
    "meeting_link": "https://meet.google.com/abc-defg-hij",
    "reminders": [
      {"method": "email", "minutes": 1440},
      {"method": "popup", "minutes": 15}
    ]
  }'
```

### List Calendar Events

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/calendar/events?start_date=2025-08-16&end_date=2025-08-23&include_lead_info=true" \
  -H "Authorization: Bearer <access-token>"
```

## Knowledge Management

### Upload Text Document

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/knowledge/documents" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product Features and Pricing",
    "content": "Our AI Secretary platform offers the following features:\n\n1. Multi-channel communication support\n2. Intelligent message routing\n3. CRM integration\n4. Calendar management\n5. Knowledge base with RAG\n\nPricing:\n- Starter: $29/month\n- Pro: $79/month\n- Enterprise: $199/month",
    "type": "text",
    "tags": ["product", "pricing", "features"],
    "category": "sales"
  }'
```

### Upload URL for Content Extraction

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/knowledge/documents" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Company Blog - AI Trends 2025",
    "type": "url",
    "source_url": "https://company.com/blog/ai-trends-2025",
    "tags": ["blog", "ai", "trends"],
    "category": "marketing"
  }'
```

### Search Knowledge Base

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/knowledge/search" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the pricing plans for the Pro version?",
    "limit": 5,
    "min_similarity": 0.7,
    "include_citations": true
  }'
```

**Response:**
```json
{
  "success": true,
  "message": "Search completed successfully",
  "data": [
    {
      "content": "Pro: $79/month - Includes advanced CRM features, calendar integration, and priority support",
      "similarity": 0.92,
      "document_id": 123,
      "document_title": "Product Features and Pricing",
      "chunk_id": 456,
      "citation": {
        "source": "Product Features and Pricing",
        "url": null,
        "created_at": "2025-08-16T10:00:00Z"
      }
    }
  ]
}
```

### List Knowledge Sources

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/knowledge/sources?status=indexed&category=sales" \
  -H "Authorization: Bearer <access-token>"
```

## Billing and Subscriptions

### List Invoices

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/billing/invoices?status=paid&start_date=2025-07-01&end_date=2025-08-16" \
  -H "Authorization: Bearer <access-token>"
```

### Create Invoice

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/billing/invoices" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_email": "client@company.com",
    "description": "AI Secretary Services - August 2025",
    "amount": 79.00,
    "currency": "USD",
    "due_date": "2025-09-15T00:00:00Z",
    "line_items": [
      {
        "description": "Pro Plan Subscription",
        "quantity": 1,
        "unit_amount": 79.00
      }
    ],
    "metadata": {
      "tenant_id": "456",
      "subscription_id": "sub_123"
    }
  }'
```

### Get Subscription Status

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/billing/subscription" \
  -H "Authorization: Bearer <access-token>"
```

### Update Subscription Plan

```bash
curl -X PUT "https://api.ai-secretary.com/api/v1/billing/subscription" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "plan": "enterprise",
    "proration_behavior": "create_prorations"
  }'
```

### Get Usage Metrics

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/billing/usage?start_date=2025-08-01&end_date=2025-08-16" \
  -H "Authorization: Bearer <access-token>"
```

## KYB Monitoring

### Add Counterparty for Monitoring

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/kyb/counterparties" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Business Ltd",
    "vat_number": "GB123456789",
    "lei_code": "213800ABCDEFGHIJKL12",
    "country": "GB",
    "business_address": "123 Business Street, London, UK",
    "monitoring_enabled": true,
    "check_frequency": "daily",
    "alert_thresholds": {
      "risk_score_increase": 20,
      "sanctions_match": true,
      "insolvency_proceedings": true,
      "vat_status_change": true
    }
  }'
```

### List Counterparties with Risk Filtering

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/kyb/counterparties?risk_level=medium&status=active&country=GB" \
  -H "Authorization: Bearer <access-token>"
```

### Get Counterparty Details with History

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/kyb/counterparties/123?include=snapshots,alerts,risk_history" \
  -H "Authorization: Bearer <access-token>"
```

### List KYB Alerts

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/kyb/alerts?severity=high&is_read=false&type=sanctions_match" \
  -H "Authorization: Bearer <access-token>"
```

### Mark Alert as Read

```bash
curl -X PUT "https://api.ai-secretary.com/api/v1/kyb/alerts/456" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "is_read": true,
    "notes": "Reviewed and confirmed false positive. Customer cleared by compliance team."
  }'
```

### Trigger Manual KYB Check

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/kyb/counterparties/123/check" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "check_types": ["vies", "sanctions", "insolvency", "lei"],
    "priority": "high"
  }'
```

## Channel Management

### Configure Telegram Bot

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/channels/telegram/configure" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
    "webhook_url": "https://api.ai-secretary.com/webhooks/telegram/456",
    "enabled": true,
    "settings": {
      "auto_response": true,
      "welcome_message": "Hello! I am your AI secretary. How can I help you today?",
      "business_hours_only": false,
      "language": "en"
    }
  }'
```

### Get Channel Status

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/channels/status" \
  -H "Authorization: Bearer <access-token>"
```

### Configure Web Widget

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/channels/widget/configure" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "enabled": true,
    "settings": {
      "theme": "modern",
      "primary_color": "#667eea",
      "position": "bottom-right",
      "welcome_message": "Hi! How can we help you?",
      "placeholder_text": "Type your message...",
      "show_agent_typing": true,
      "collect_email": true,
      "offline_message": "We are currently offline. Please leave a message and we will get back to you soon."
    },
    "allowed_domains": ["company.com", "www.company.com"]
  }'
```

## Notifications

### Send Notification

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/notifications" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "lead_created",
    "title": "New Lead Created",
    "message": "A new lead has been created from web widget inquiry",
    "channels": ["email", "telegram"],
    "recipients": [123, 456],
    "data": {
      "lead_id": 789,
      "lead_name": "John Prospect",
      "lead_email": "john@prospect.com",
      "source": "web_widget"
    },
    "priority": "normal",
    "schedule_at": null
  }'
```

### Get Notification Preferences

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/notifications/preferences" \
  -H "Authorization: Bearer <access-token>"
```

### Update Notification Preferences

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/notifications/preferences" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email_notifications": true,
    "telegram_notifications": true,
    "push_notifications": false,
    "notification_types": {
      "new_lead": true,
      "task_due": true,
      "kyb_alert": true,
      "system_maintenance": true,
      "billing_reminder": true
    },
    "quiet_hours": {
      "enabled": true,
      "start": "22:00",
      "end": "08:00",
      "timezone": "America/New_York"
    }
  }'
```

## GDPR Compliance

### Grant Consent

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/gdpr/consent/grant" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_email": "customer@example.com",
    "consent_types": ["marketing", "analytics", "data_processing"],
    "purpose": "Customer communication and service improvement",
    "legal_basis": "consent",
    "source": "web_form",
    "ip_address": "192.168.1.100",
    "user_agent": "Mozilla/5.0..."
  }'
```

### Request Data Export

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/gdpr/data-export" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_email": "customer@example.com",
    "data_types": ["personal_info", "communication_history", "crm_data"],
    "format": "json",
    "include_metadata": true
  }'
```

### Request Data Deletion

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/gdpr/deletion-request" \
  -H "Authorization: Bearer <access-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "contact_email": "customer@example.com",
    "deletion_type": "complete",
    "reason": "Customer request",
    "retain_legal_basis": false,
    "confirmation_required": true
  }'
```

### Get Retention Policies

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/gdpr/retention/policies" \
  -H "Authorization: Bearer <access-token>"
```

## Monitoring and Analytics

### Get System Metrics

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/monitoring/metrics" \
  -H "Authorization: Bearer <access-token>"
```

### Get Endpoint Performance

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/monitoring/metrics/endpoint/crm/leads?minutes=60" \
  -H "Authorization: Bearer <access-token>"
```

### Get Detailed Health Information

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/monitoring/health/detailed" \
  -H "Authorization: Bearer <access-token>"
```

### Get Application Logs

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/monitoring/logs?level=ERROR&limit=50" \
  -H "Authorization: Bearer <access-token>"
```

## Error Handling Examples

### Handling Rate Limits

```python
import requests
import time

def make_api_request_with_retry(url, headers, data=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data) if data else requests.get(url, headers=headers)
            
            if response.status_code == 429:
                # Rate limited
                retry_after = int(response.headers.get('Retry-After', 60))
                print(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            
            return response
        
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("Max retries exceeded")
```

### Handling Validation Errors

```python
def handle_api_response(response):
    if response.status_code == 200 or response.status_code == 201:
        return response.json()
    elif response.status_code == 400:
        error_data = response.json()
        if 'error' in error_data and 'details' in error_data['error']:
            # Handle validation errors
            validation_errors = error_data['error']['details']
            for field, errors in validation_errors.items():
                print(f"Validation error in {field}: {', '.join(errors)}")
        raise ValueError(f"Validation error: {error_data['error']['message']}")
    elif response.status_code == 401:
        raise Exception("Authentication failed. Please check your token.")
    elif response.status_code == 403:
        raise Exception("Insufficient permissions for this operation.")
    elif response.status_code == 404:
        raise Exception("Resource not found.")
    else:
        error_data = response.json()
        raise Exception(f"API Error: {error_data.get('error', {}).get('message', 'Unknown error')}")
```

## Webhook Examples

### Webhook Event Types

The API sends webhooks for the following events:

- `lead.created` - New lead created
- `lead.updated` - Lead information updated
- `lead.status_changed` - Lead status or stage changed
- `message.received` - New message received
- `message.responded` - AI response generated
- `task.created` - New task created
- `task.completed` - Task marked as completed
- `invoice.paid` - Invoice payment received
- `subscription.updated` - Subscription plan changed
- `kyb.alert_created` - New KYB alert generated
- `calendar.event_created` - Calendar event created
- `notification.sent` - Notification delivered

### Webhook Handler Example (Flask)

```python
from flask import Flask, request, jsonify
import hmac
import hashlib
import os

app = Flask(__name__)

def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature for security."""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

@app.route('/webhook/ai-secretary', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data(as_text=True)
    
    if not verify_webhook_signature(payload, signature, os.environ['WEBHOOK_SECRET']):
        return jsonify({'error': 'Invalid signature'}), 401
    
    event_data = request.get_json()
    
    # Handle different event types
    if event_data['type'] == 'lead.created':
        handle_lead_created(event_data['data'])
    elif event_data['type'] == 'message.received':
        handle_message_received(event_data['data'])
    elif event_data['type'] == 'kyb.alert_created':
        handle_kyb_alert(event_data['data'])
    
    return jsonify({'status': 'success'})

def handle_lead_created(lead_data):
    """Handle new lead creation."""
    print(f"New lead created: {lead_data['contact']['name']} from {lead_data['source']}")
    # Add your custom logic here

def handle_message_received(message_data):
    """Handle new message."""
    print(f"New message from {message_data['customer_name']}: {message_data['content']}")
    # Add your custom logic here

def handle_kyb_alert(alert_data):
    """Handle KYB alert."""
    print(f"KYB Alert: {alert_data['type']} for {alert_data['counterparty_name']}")
    # Add your custom logic here

if __name__ == '__main__':
    app.run(debug=True)
```

This comprehensive guide covers all major API functionality with practical examples. For more specific use cases or advanced integrations, refer to the interactive API documentation or contact our support team.