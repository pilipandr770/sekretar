# AI Secretary SaaS API - Developer Onboarding Guide

Welcome to the AI Secretary SaaS API! This guide will help you get started with integrating our comprehensive AI-powered business automation platform into your applications.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Getting Your API Credentials](#getting-your-api-credentials)
3. [Development Environment Setup](#development-environment-setup)
4. [Your First API Call](#your-first-api-call)
5. [Core Concepts](#core-concepts)
6. [Integration Patterns](#integration-patterns)
7. [SDKs and Libraries](#sdks-and-libraries)
8. [Testing and Debugging](#testing-and-debugging)
9. [Best Practices](#best-practices)
10. [Common Use Cases](#common-use-cases)
11. [Troubleshooting](#troubleshooting)
12. [Next Steps](#next-steps)

## Quick Start

### 1. Create Your Account

Visit [AI Secretary SaaS](https://ai-secretary.com) and sign up for a free 3-day trial account. You'll get:

- Full access to all API endpoints
- 1,000 API calls per day during trial
- Access to all AI agents and features
- Multi-channel communication setup
- CRM and knowledge base functionality

### 2. Get Your API Credentials

After registration, you'll receive:
- **Access Token**: For authenticating API requests
- **Refresh Token**: For renewing expired access tokens
- **Tenant ID**: Your organization identifier
- **Webhook Secret**: For verifying webhook signatures

### 3. Make Your First Call

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Getting Your API Credentials

### Option 1: Web Dashboard

1. Log into your [AI Secretary Dashboard](https://app.ai-secretary.com)
2. Navigate to **Settings** → **API Keys**
3. Click **Generate New API Key**
4. Copy your credentials securely

### Option 2: API Registration

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@company.com",
    "password": "SecurePassword123!",
    "organization_name": "Your Company Name",
    "first_name": "Your",
    "last_name": "Name"
  }'
```

**Response includes your tokens:**
```json
{
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "user": { ... },
    "tenant": { ... }
  }
}
```

## Development Environment Setup

### Environment Variables

Create a `.env` file in your project:

```bash
# AI Secretary API Configuration
AI_SECRETARY_API_URL=https://api.ai-secretary.com/api/v1
AI_SECRETARY_ACCESS_TOKEN=your_access_token_here
AI_SECRETARY_REFRESH_TOKEN=your_refresh_token_here
AI_SECRETARY_WEBHOOK_SECRET=your_webhook_secret_here

# Optional: Development settings
AI_SECRETARY_DEBUG=true
AI_SECRETARY_TIMEOUT=30
AI_SECRETARY_RETRY_ATTEMPTS=3
```

### Language-Specific Setup

#### Python

```bash
pip install requests python-dotenv
```

```python
import os
import requests
from dotenv import load_dotenv

load_dotenv()

class AISecretaryClient:
    def __init__(self):
        self.base_url = os.getenv('AI_SECRETARY_API_URL')
        self.access_token = os.getenv('AI_SECRETARY_ACCESS_TOKEN')
        self.headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
    
    def get(self, endpoint):
        response = requests.get(f'{self.base_url}{endpoint}', headers=self.headers)
        return response.json()
    
    def post(self, endpoint, data):
        response = requests.post(f'{self.base_url}{endpoint}', headers=self.headers, json=data)
        return response.json()

# Usage
client = AISecretaryClient()
profile = client.get('/auth/me')
print(f"Welcome, {profile['data']['user']['first_name']}!")
```

#### Node.js

```bash
npm install axios dotenv
```

```javascript
require('dotenv').config();
const axios = require('axios');

class AISecretaryClient {
    constructor() {
        this.baseURL = process.env.AI_SECRETARY_API_URL;
        this.accessToken = process.env.AI_SECRETARY_ACCESS_TOKEN;
        this.headers = {
            'Authorization': `Bearer ${this.accessToken}`,
            'Content-Type': 'application/json'
        };
    }

    async get(endpoint) {
        const response = await axios.get(`${this.baseURL}${endpoint}`, { headers: this.headers });
        return response.data;
    }

    async post(endpoint, data) {
        const response = await axios.post(`${this.baseURL}${endpoint}`, data, { headers: this.headers });
        return response.data;
    }
}

// Usage
const client = new AISecretaryClient();
client.get('/auth/me').then(profile => {
    console.log(`Welcome, ${profile.data.user.first_name}!`);
});
```

#### PHP

```php
<?php
require_once 'vendor/autoload.php';

use GuzzleHttp\Client;
use Dotenv\Dotenv;

$dotenv = Dotenv::createImmutable(__DIR__);
$dotenv->load();

class AISecretaryClient {
    private $client;
    private $baseUrl;
    private $headers;

    public function __construct() {
        $this->baseUrl = $_ENV['AI_SECRETARY_API_URL'];
        $this->headers = [
            'Authorization' => 'Bearer ' . $_ENV['AI_SECRETARY_ACCESS_TOKEN'],
            'Content-Type' => 'application/json'
        ];
        $this->client = new Client();
    }

    public function get($endpoint) {
        $response = $this->client->get($this->baseUrl . $endpoint, [
            'headers' => $this->headers
        ]);
        return json_decode($response->getBody(), true);
    }

    public function post($endpoint, $data) {
        $response = $this->client->post($this->baseUrl . $endpoint, [
            'headers' => $this->headers,
            'json' => $data
        ]);
        return json_decode($response->getBody(), true);
    }
}

// Usage
$client = new AISecretaryClient();
$profile = $client->get('/auth/me');
echo "Welcome, " . $profile['data']['user']['first_name'] . "!\n";
?>
```

## Your First API Call

Let's start with a simple health check and then get your profile information:

### 1. Health Check (No Authentication Required)

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/health"
```

**Expected Response:**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-16T12:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": {"status": "healthy", "response_time_ms": 15},
    "redis": {"status": "healthy", "response_time_ms": 5}
  }
}
```

### 2. Get Your Profile (Authentication Required)

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/auth/me" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Expected Response:**
```json
{
  "success": true,
  "message": "Profile retrieved successfully",
  "data": {
    "user": {
      "id": 123,
      "email": "your-email@company.com",
      "first_name": "Your",
      "last_name": "Name",
      "role": "owner",
      "language": "en"
    },
    "tenant": {
      "id": 456,
      "name": "Your Company Name",
      "subscription_status": "trial",
      "trial_ends_at": "2025-08-19T12:00:00Z"
    }
  }
}
```

### 3. Create Your First Lead

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/crm/leads" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "contact": {
      "name": "John Prospect",
      "email": "john@prospect.com",
      "phone": "+1-555-0123",
      "company": "Prospect Corp"
    },
    "source": "api_integration",
    "value": 5000,
    "notes": "Lead created via API integration test"
  }'
```

## Core Concepts

### 1. Multi-Tenant Architecture

Every API request operates within a tenant context. Your tenant ID is automatically determined from your access token.

```python
# All operations are automatically scoped to your tenant
leads = client.get('/crm/leads')  # Only returns your tenant's leads
```

### 2. Role-Based Access Control

Users have different roles with varying permissions:

- **Owner**: Full access to all features
- **Manager**: Access to CRM, inbox, calendar, knowledge
- **Support**: Access to inbox, CRM (read-only), knowledge
- **Accounting**: Access to billing, invoices, basic CRM
- **Read-only**: View-only access to most features

### 3. AI Agent System

The platform uses multiple specialized AI agents:

- **Router Agent**: Detects intent and routes messages
- **Supervisor Agent**: Filters content and ensures compliance
- **Sales Agent**: Handles sales inquiries and lead qualification
- **Support Agent**: Provides technical support and troubleshooting
- **Billing Agent**: Manages subscription and payment inquiries
- **Operations Agent**: Handles general business operations

### 4. Multi-Channel Communication

Messages can come from various channels:

- **Telegram**: Bot integration with inline keyboards
- **Signal**: CLI-based messaging
- **Web Widget**: JavaScript widget for websites
- **Email**: SMTP integration (coming soon)

### 5. Knowledge Base with RAG

The system uses Retrieval-Augmented Generation (RAG) for intelligent responses:

```python
# Upload knowledge
client.post('/knowledge/documents', {
    'title': 'Product FAQ',
    'content': 'Q: What is AI Secretary? A: It is a comprehensive...',
    'type': 'text'
})

# Search knowledge
results = client.post('/knowledge/search', {
    'query': 'What features does the product have?',
    'limit': 5
})
```

## Integration Patterns

### 1. Customer Inquiry Processing

```python
def process_customer_inquiry(customer_email, message, channel='web_widget'):
    # Create inbox message
    message_response = client.post('/inbox/messages', {
        'content': message,
        'channel': channel,
        'customer_email': customer_email,
        'customer_name': extract_name_from_email(customer_email)
    })
    
    # Check if lead was auto-created
    leads = client.get(f'/crm/leads?contact_email={customer_email}')
    
    if not leads['data']:
        # Create lead manually
        lead = client.post('/crm/leads', {
            'contact': {
                'name': extract_name_from_email(customer_email),
                'email': customer_email
            },
            'source': channel,
            'notes': f'Initial inquiry: {message[:100]}...'
        })
        return lead
    
    return leads['data'][0]
```

### 2. CRM Synchronization

```python
def sync_external_crm_data(external_leads):
    results = []
    
    for external_lead in external_leads:
        # Check if lead exists
        existing = client.get(f'/crm/leads?contact_email={external_lead["email"]}')
        
        if existing['data']:
            # Update existing lead
            updated = client.put(f'/crm/leads/{existing["data"][0]["id"]}', {
                'value': external_lead['value'],
                'status': external_lead['status']
            })
            results.append({'action': 'updated', 'lead': updated})
        else:
            # Create new lead
            created = client.post('/crm/leads', {
                'contact': external_lead['contact'],
                'source': 'external_crm',
                'value': external_lead['value']
            })
            results.append({'action': 'created', 'lead': created})
    
    return results
```

### 3. Webhook Event Handling

```python
from flask import Flask, request, jsonify
import hmac
import hashlib

app = Flask(__name__)

@app.route('/webhook/ai-secretary', methods=['POST'])
def handle_webhook():
    # Verify signature
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data(as_text=True)
    
    if not verify_signature(payload, signature):
        return jsonify({'error': 'Invalid signature'}), 401
    
    event = request.get_json()
    
    # Handle different event types
    handlers = {
        'lead.created': handle_lead_created,
        'message.received': handle_message_received,
        'task.due': handle_task_due,
        'kyb.alert_created': handle_kyb_alert
    }
    
    handler = handlers.get(event['type'])
    if handler:
        handler(event['data'])
    
    return jsonify({'status': 'success'})

def handle_lead_created(lead_data):
    # Send notification to sales team
    send_slack_notification(f"New lead: {lead_data['contact']['name']}")
    
    # Create follow-up task
    client.post('/crm/tasks', {
        'title': f'Follow up with {lead_data["contact"]["name"]}',
        'lead_id': lead_data['id'],
        'due_date': (datetime.now() + timedelta(hours=24)).isoformat(),
        'priority': 'high'
    })
```

## SDKs and Libraries

### Official SDKs (Coming Soon)

We're working on official SDKs for popular languages:

- **Python SDK**: `pip install ai-secretary-sdk`
- **Node.js SDK**: `npm install ai-secretary-sdk`
- **PHP SDK**: `composer require ai-secretary/sdk`
- **Go SDK**: `go get github.com/ai-secretary/go-sdk`

### Community Libraries

Check our [GitHub organization](https://github.com/ai-secretary) for community-contributed libraries and examples.

### Postman Collection

Import our [Postman collection](https://api.ai-secretary.com/postman/collection.json) for easy API testing:

1. Open Postman
2. Click **Import**
3. Enter URL: `https://api.ai-secretary.com/postman/collection.json`
4. Set your environment variables:
   - `base_url`: `https://api.ai-secretary.com/api/v1`
   - `access_token`: Your access token

## Testing and Debugging

### 1. Use the Interactive Documentation

Visit our [interactive API docs](https://docs.ai-secretary.com/api) to test endpoints directly in your browser.

### 2. Enable Debug Mode

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)

# Add request/response logging
import requests
import http.client as http_client
http_client.HTTPConnection.debuglevel = 1
```

### 3. Test with Sandbox Data

Use our test endpoints for safe experimentation:

```bash
# Create test lead (won't affect real data)
curl -X POST "https://api.ai-secretary.com/api/v1/test/crm/leads" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"contact": {"name": "Test Lead", "email": "test@example.com"}}'
```

### 4. Monitor API Usage

Check your API usage in the dashboard:

```python
# Get usage statistics
usage = client.get('/billing/usage?start_date=2025-08-01&end_date=2025-08-16')
print(f"API calls this month: {usage['data']['total_requests']}")
print(f"Remaining quota: {usage['data']['remaining_quota']}")
```

## Best Practices

### 1. Authentication Management

```python
class TokenManager:
    def __init__(self, access_token, refresh_token):
        self.access_token = access_token
        self.refresh_token = refresh_token
        self.expires_at = None
    
    def get_valid_token(self):
        if self.is_token_expired():
            self.refresh_access_token()
        return self.access_token
    
    def refresh_access_token(self):
        response = requests.post(
            'https://api.ai-secretary.com/api/v1/auth/refresh',
            headers={'Authorization': f'Bearer {self.refresh_token}'}
        )
        data = response.json()
        self.access_token = data['data']['access_token']
        # Update expires_at based on JWT payload
```

### 2. Error Handling

```python
def make_api_request(method, endpoint, data=None):
    try:
        response = requests.request(method, f'{base_url}{endpoint}', 
                                  headers=headers, json=data)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            # Token expired, refresh and retry
            refresh_token()
            return make_api_request(method, endpoint, data)
        elif response.status_code == 429:
            # Rate limited, wait and retry
            time.sleep(int(response.headers.get('Retry-After', 60)))
            return make_api_request(method, endpoint, data)
        else:
            handle_api_error(response)
    
    except requests.exceptions.RequestException as e:
        handle_network_error(e)
```

### 3. Pagination Handling

```python
def get_all_leads():
    all_leads = []
    page = 1
    
    while True:
        response = client.get(f'/crm/leads?page={page}&per_page=100')
        leads = response['data']
        all_leads.extend(leads)
        
        if not response['pagination']['has_next']:
            break
        
        page += 1
    
    return all_leads
```

### 4. Rate Limiting

```python
import time
from functools import wraps

def rate_limit(calls_per_minute=60):
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            left_to_wait = min_interval - elapsed
            if left_to_wait > 0:
                time.sleep(left_to_wait)
            ret = func(*args, **kwargs)
            last_called[0] = time.time()
            return ret
        return wrapper
    return decorator

@rate_limit(calls_per_minute=50)
def api_call(endpoint):
    return client.get(endpoint)
```

## Common Use Cases

### 1. Customer Support Automation

```python
def setup_customer_support():
    # Configure web widget
    client.post('/channels/widget/configure', {
        'enabled': True,
        'settings': {
            'welcome_message': 'Hi! How can we help you today?',
            'auto_response': True,
            'collect_email': True
        }
    })
    
    # Upload support knowledge base
    with open('support_faq.md', 'r') as f:
        client.post('/knowledge/documents', {
            'title': 'Support FAQ',
            'content': f.read(),
            'type': 'text',
            'category': 'support'
        })
```

### 2. Sales Pipeline Management

```python
def manage_sales_pipeline():
    # Get leads in proposal stage
    leads = client.get('/crm/leads?stage_id=3&status=proposal')
    
    for lead in leads['data']:
        # Create follow-up task if no recent activity
        last_activity = datetime.fromisoformat(lead['updated_at'])
        if (datetime.now() - last_activity).days > 3:
            client.post('/crm/tasks', {
                'title': f'Follow up on proposal - {lead["contact"]["name"]}',
                'lead_id': lead['id'],
                'priority': 'high',
                'due_date': (datetime.now() + timedelta(days=1)).isoformat()
            })
```

### 3. Compliance Monitoring

```python
def setup_kyb_monitoring():
    # Add counterparties for monitoring
    counterparties = [
        {'name': 'Supplier A', 'vat_number': 'GB123456789', 'country': 'GB'},
        {'name': 'Client B', 'lei_code': '213800ABCDEFGHIJKL12', 'country': 'DE'}
    ]
    
    for cp in counterparties:
        client.post('/kyb/counterparties', {
            **cp,
            'monitoring_enabled': True,
            'check_frequency': 'daily'
        })
    
    # Set up alert notifications
    client.post('/notifications/preferences', {
        'notification_types': {
            'kyb_alert': True
        },
        'channels': ['email', 'telegram']
    })
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors (401)

```python
# Check token validity
try:
    profile = client.get('/auth/me')
    print("Token is valid")
except requests.exceptions.HTTPError as e:
    if e.response.status_code == 401:
        print("Token expired or invalid - refreshing...")
        # Refresh token logic here
```

#### 2. Rate Limiting (429)

```python
# Handle rate limits gracefully
def handle_rate_limit(response):
    if response.status_code == 429:
        retry_after = int(response.headers.get('Retry-After', 60))
        print(f"Rate limited. Waiting {retry_after} seconds...")
        time.sleep(retry_after)
        return True
    return False
```

#### 3. Validation Errors (400)

```python
# Parse validation errors
def handle_validation_error(response):
    if response.status_code == 400:
        error_data = response.json()
        if 'details' in error_data.get('error', {}):
            for field, errors in error_data['error']['details'].items():
                print(f"Validation error in {field}: {', '.join(errors)}")
```

### Debug Checklist

- [ ] Check API endpoint URL is correct
- [ ] Verify access token is valid and not expired
- [ ] Ensure Content-Type header is set to `application/json`
- [ ] Validate request payload against API schema
- [ ] Check rate limit headers in response
- [ ] Verify tenant permissions for the operation
- [ ] Test with a simple GET request first

### Getting Help

1. **Documentation**: [https://docs.ai-secretary.com](https://docs.ai-secretary.com)
2. **API Status**: [https://status.ai-secretary.com](https://status.ai-secretary.com)
3. **Support Email**: [api-support@ai-secretary.com](mailto:api-support@ai-secretary.com)
4. **Community Forum**: [https://community.ai-secretary.com](https://community.ai-secretary.com)
5. **GitHub Issues**: [https://github.com/ai-secretary/api-issues](https://github.com/ai-secretary/api-issues)

## Next Steps

### 1. Explore Advanced Features

- Set up webhook endpoints for real-time notifications
- Implement multi-channel communication flows
- Configure AI agent customization
- Set up KYB monitoring for compliance

### 2. Production Deployment

- Move from trial to paid subscription
- Set up monitoring and alerting
- Implement proper error handling and logging
- Configure backup and disaster recovery

### 3. Scale Your Integration

- Implement caching for frequently accessed data
- Set up batch processing for bulk operations
- Optimize API calls with proper pagination
- Monitor usage and performance metrics

### 4. Join the Community

- Follow our [blog](https://blog.ai-secretary.com) for updates
- Join our [Discord community](https://discord.gg/ai-secretary)
- Contribute to open-source projects
- Share your integration stories

---

**Welcome to the AI Secretary ecosystem!** We're excited to see what you'll build with our API. If you have any questions or need assistance, don't hesitate to reach out to our support team.

Happy coding! 🚀