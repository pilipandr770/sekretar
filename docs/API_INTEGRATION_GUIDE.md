# AI Secretary SaaS API Integration Guide

This guide provides comprehensive examples and best practices for integrating with the AI Secretary SaaS API.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [Common Integration Patterns](#common-integration-patterns)
4. [API Usage Examples](#api-usage-examples)
5. [Error Handling](#error-handling)
6. [Rate Limiting](#rate-limiting)
7. [Webhooks](#webhooks)
8. [SDKs and Libraries](#sdks-and-libraries)
9. [Testing](#testing)
10. [Best Practices](#best-practices)

## Getting Started

### Base URLs

- **Production**: `https://api.ai-secretary.com/api/v1`
- **Staging**: `https://staging-api.ai-secretary.com/api/v1`
- **Development**: `http://localhost:5000/api/v1`

### Prerequisites

1. Create an account at [AI Secretary SaaS](https://ai-secretary.com)
2. Obtain API credentials from your tenant settings
3. Set up your development environment

### Quick Start Example

```bash
# Check API health
curl -X GET "https://api.ai-secretary.com/api/v1/health"

# Get API information
curl -X GET "https://api.ai-secretary.com/"
```

## Authentication

The API uses JWT Bearer tokens for authentication. You'll need to obtain an access token by logging in with your credentials.

### Login and Get Token

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@example.com",
    "password": "your-password"
  }'
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "user": {
    "id": 123,
    "email": "your-email@example.com",
    "first_name": "John",
    "last_name": "Doe",
    "role": "manager"
  }
}
```

### Using the Token

Include the access token in the Authorization header for all authenticated requests:

```bash
curl -X GET "https://api.ai-secretary.com/api/v1/crm/leads" \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..." \
  -H "Content-Type: application/json"
```

### Token Refresh

Access tokens expire after a certain period. Use the refresh token to get a new access token:

```bash
curl -X POST "https://api.ai-secretary.com/api/v1/auth/refresh" \
  -H "Authorization: Bearer <refresh-token>" \
  -H "Content-Type: application/json"
```

## Common Integration Patterns

### 1. Customer Inquiry Processing

This pattern demonstrates how to handle incoming customer inquiries and create leads automatically.

```python
import requests
import json

class AISecretaryClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def process_customer_inquiry(self, customer_email, customer_name, message, channel='web_widget'):
        """Process incoming customer inquiry and create lead if needed."""
        
        # Step 1: Create inbox message
        message_data = {
            'content': message,
            'channel': channel,
            'customer_email': customer_email,
            'customer_name': customer_name
        }
        
        response = requests.post(
            f'{self.base_url}/inbox/messages',
            headers=self.headers,
            json=message_data
        )
        
        if response.status_code == 201:
            message_result = response.json()
            print(f"Message created: {message_result['data']['id']}")
            
            # Step 2: Check if lead was auto-created
            leads_response = requests.get(
                f'{self.base_url}/crm/leads?contact_email={customer_email}',
                headers=self.headers
            )
            
            if leads_response.status_code == 200:
                leads = leads_response.json()['data']
                if leads:
                    print(f"Lead found: {leads[0]['id']}")
                    return leads[0]
                else:
                    # Step 3: Create lead manually if not auto-created
                    return self.create_lead_from_inquiry(customer_email, customer_name, message)
        
        return None
    
    def create_lead_from_inquiry(self, email, name, message):
        """Create a lead from customer inquiry."""
        lead_data = {
            'contact': {
                'name': name,
                'email': email
            },
            'source': 'api_integration',
            'value': 0,  # To be qualified later
            'notes': f'Initial inquiry: {message[:100]}...'
        }
        
        response = requests.post(
            f'{self.base_url}/crm/leads',
            headers=self.headers,
            json=lead_data
        )
        
        if response.status_code == 201:
            lead = response.json()['data']
            print(f"Lead created: {lead['id']}")
            return lead
        
        return None

# Usage example
client = AISecretaryClient('https://api.ai-secretary.com/api/v1', 'your-access-token')
lead = client.process_customer_inquiry(
    customer_email='prospect@example.com',
    customer_name='John Prospect',
    message='Hi, I\'m interested in your AI secretary services for my business.',
    channel='web_widget'
)
```

### 2. CRM Integration

Sync leads and contacts with your existing CRM system.

```javascript
class CRMSync {
    constructor(apiBaseUrl, accessToken) {
        this.apiBaseUrl = apiBaseUrl;
        this.headers = {
            'Authorization': `Bearer ${accessToken}`,
            'Content-Type': 'application/json'
        };
    }

    async syncLeadsFromExternalCRM(externalLeads) {
        const results = [];
        
        for (const externalLead of externalLeads) {
            try {
                // Check if lead already exists
                const existingLead = await this.findLeadByEmail(externalLead.email);
                
                if (existingLead) {
                    // Update existing lead
                    const updated = await this.updateLead(existingLead.id, externalLead);
                    results.push({ action: 'updated', lead: updated });
                } else {
                    // Create new lead
                    const created = await this.createLead(externalLead);
                    results.push({ action: 'created', lead: created });
                }
            } catch (error) {
                results.push({ action: 'error', error: error.message, data: externalLead });
            }
        }
        
        return results;
    }

    async findLeadByEmail(email) {
        const response = await fetch(
            `${this.apiBaseUrl}/crm/leads?contact_email=${encodeURIComponent(email)}`,
            { headers: this.headers }
        );
        
        if (response.ok) {
            const data = await response.json();
            return data.data.length > 0 ? data.data[0] : null;
        }
        
        return null;
    }

    async createLead(leadData) {
        const response = await fetch(`${this.apiBaseUrl}/crm/leads`, {
            method: 'POST',
            headers: this.headers,
            body: JSON.stringify({
                contact: {
                    name: leadData.name,
                    email: leadData.email,
                    phone: leadData.phone,
                    company: leadData.company
                },
                source: leadData.source || 'external_crm',
                value: leadData.value || 0,
                status: leadData.status || 'new'
            })
        });

        if (response.ok) {
            const result = await response.json();
            return result.data;
        }

        throw new Error(`Failed to create lead: ${response.statusText}`);
    }

    async updateLead(leadId, leadData) {
        const response = await fetch(`${this.apiBaseUrl}/crm/leads/${leadId}`, {
            method: 'PUT',
            headers: this.headers,
            body: JSON.stringify({
                value: leadData.value,
                status: leadData.status,
                stage_id: leadData.stage_id
            })
        });

        if (response.ok) {
            const result = await response.json();
            return result.data;
        }

        throw new Error(`Failed to update lead: ${response.statusText}`);
    }
}

// Usage example
const crmSync = new CRMSync('https://api.ai-secretary.com/api/v1', 'your-access-token');

const externalLeads = [
    {
        name: 'Jane Smith',
        email: 'jane@example.com',
        phone: '+1234567890',
        company: 'Example Corp',
        source: 'salesforce',
        value: 10000,
        status: 'qualified'
    }
];

crmSync.syncLeadsFromExternalCRM(externalLeads)
    .then(results => console.log('Sync results:', results))
    .catch(error => console.error('Sync failed:', error));
```

### 3. Knowledge Base Integration

Upload and manage knowledge base documents for AI responses.

```python
import requests
import os
from typing import List, Dict

class KnowledgeBaseManager:
    def __init__(self, base_url: str, access_token: str):
        self.base_url = base_url
        self.headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
    
    def upload_text_document(self, title: str, content: str) -> Dict:
        """Upload a text document to the knowledge base."""
        document_data = {
            'title': title,
            'content': content,
            'type': 'text'
        }
        
        response = requests.post(
            f'{self.base_url}/knowledge/documents',
            headers=self.headers,
            json=document_data
        )
        
        if response.status_code == 201:
            return response.json()['data']
        else:
            raise Exception(f"Failed to upload document: {response.text}")
    
    def upload_url_document(self, title: str, url: str) -> Dict:
        """Upload a URL for content extraction."""
        document_data = {
            'title': title,
            'type': 'url',
            'source_url': url
        }
        
        response = requests.post(
            f'{self.base_url}/knowledge/documents',
            headers=self.headers,
            json=document_data
        )
        
        if response.status_code == 201:
            return response.json()['data']
        else:
            raise Exception(f"Failed to upload URL: {response.text}")
    
    def search_knowledge_base(self, query: str, limit: int = 5) -> List[Dict]:
        """Search the knowledge base."""
        search_data = {
            'query': query,
            'limit': limit,
            'min_similarity': 0.7
        }
        
        response = requests.post(
            f'{self.base_url}/knowledge/search',
            headers=self.headers,
            json=search_data
        )
        
        if response.status_code == 200:
            return response.json()['data']
        else:
            raise Exception(f"Search failed: {response.text}")
    
    def bulk_upload_from_directory(self, directory_path: str) -> List[Dict]:
        """Upload all text files from a directory."""
        results = []
        
        for filename in os.listdir(directory_path):
            if filename.endswith('.txt') or filename.endswith('.md'):
                file_path = os.path.join(directory_path, filename)
                
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    title = os.path.splitext(filename)[0]
                    
                    try:
                        document = self.upload_text_document(title, content)
                        results.append({
                            'filename': filename,
                            'status': 'success',
                            'document_id': document['id']
                        })
                    except Exception as e:
                        results.append({
                            'filename': filename,
                            'status': 'error',
                            'error': str(e)
                        })
        
        return results

# Usage example
kb_manager = KnowledgeBaseManager('https://api.ai-secretary.com/api/v1', 'your-access-token')

# Upload a single document
document = kb_manager.upload_text_document(
    title='Product Features',
    content='Our AI secretary supports multiple communication channels including Telegram, Signal, and web widgets...'
)
print(f"Document uploaded: {document['id']}")

# Search the knowledge base
results = kb_manager.search_knowledge_base('What channels do you support?')
for result in results:
    print(f"Found: {result['content'][:100]}... (similarity: {result['similarity']:.2f})")

# Bulk upload from directory
upload_results = kb_manager.bulk_upload_from_directory('./docs')
print(f"Uploaded {len([r for r in upload_results if r['status'] == 'success'])} documents")
```

## API Usage Examples

### Inbox Management

```bash
# List all messages
curl -X GET "https://api.ai-secretary.com/api/v1/inbox/messages?page=1&per_page=20" \
  -H "Authorization: Bearer <token>"

# Filter messages by channel
curl -X GET "https://api.ai-secretary.com/api/v1/inbox/messages?channel=telegram&status=new" \
  -H "Authorization: Bearer <token>"

# Create a new message
curl -X POST "https://api.ai-secretary.com/api/v1/inbox/messages" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Customer inquiry about pricing",
    "channel": "web_widget",
    "customer_email": "customer@example.com",
    "customer_name": "John Customer"
  }'

# Update message status
curl -X PUT "https://api.ai-secretary.com/api/v1/inbox/messages/123" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "resolved",
    "response": "Thank you for your inquiry. We have sent you detailed pricing information."
  }'
```

### CRM Operations

```bash
# List leads with filters
curl -X GET "https://api.ai-secretary.com/api/v1/crm/leads?status=qualified&source=website" \
  -H "Authorization: Bearer <token>"

# Create a new lead
curl -X POST "https://api.ai-secretary.com/api/v1/crm/leads" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "contact": {
      "name": "Jane Prospect",
      "email": "jane@prospect.com",
      "phone": "+1234567890",
      "company": "Prospect Corp"
    },
    "source": "referral",
    "value": 15000,
    "pipeline_id": 1,
    "stage_id": 2
  }'

# Update lead status
curl -X PUT "https://api.ai-secretary.com/api/v1/crm/leads/123" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "proposal",
    "value": 20000,
    "stage_id": 3
  }'

# Add note to lead
curl -X POST "https://api.ai-secretary.com/api/v1/crm/leads/123/notes" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Had a great call with the prospect. They are very interested in our Pro plan.",
    "type": "call"
  }'
```

### Calendar Integration

```bash
# Get available time slots
curl -X GET "https://api.ai-secretary.com/api/v1/calendar/availability?date=2025-08-20&duration=60" \
  -H "Authorization: Bearer <token>"

# Create calendar event
curl -X POST "https://api.ai-secretary.com/api/v1/calendar/events" \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Product Demo",
    "description": "Demo call with Jane Prospect",
    "start_time": "2025-08-20T10:00:00Z",
    "end_time": "2025-08-20T11:00:00Z",
    "attendee_email": "jane@prospect.com",
    "lead_id": 123
  }'

# List calendar events
curl -X GET "https://api.ai-secretary.com/api/v1/calendar/events?start_date=2025-08-16&end_date=2025-08-23" \
  -H "Authorization: Bearer <token>"
```

## Error Handling

The API returns consistent error responses with detailed information:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid input data",
    "details": {
      "field": "email",
      "reason": "Invalid email format"
    },
    "request_id": "req_123456789"
  }
}
```

### Common Error Codes

- `UNAUTHORIZED` (401): Authentication required or invalid token
- `FORBIDDEN` (403): Insufficient permissions
- `NOT_FOUND` (404): Resource not found
- `VALIDATION_ERROR` (400): Invalid input data
- `RATE_LIMIT_EXCEEDED` (429): Too many requests
- `INTERNAL_ERROR` (500): Server error

### Error Handling Example

```python
import requests

def make_api_request(url, headers, data=None):
    try:
        if data:
            response = requests.post(url, headers=headers, json=data)
        else:
            response = requests.get(url, headers=headers)
        
        if response.status_code == 200 or response.status_code == 201:
            return response.json()
        elif response.status_code == 401:
            raise Exception("Authentication failed. Please check your token.")
        elif response.status_code == 403:
            raise Exception("Insufficient permissions for this operation.")
        elif response.status_code == 404:
            raise Exception("Resource not found.")
        elif response.status_code == 429:
            raise Exception("Rate limit exceeded. Please wait before retrying.")
        else:
            error_data = response.json()
            error_message = error_data.get('error', {}).get('message', 'Unknown error')
            raise Exception(f"API Error: {error_message}")
    
    except requests.exceptions.RequestException as e:
        raise Exception(f"Network error: {str(e)}")
```

## Rate Limiting

The API implements rate limiting to ensure fair usage. Rate limit information is included in response headers:

- `X-RateLimit-Limit`: Request limit per window
- `X-RateLimit-Remaining`: Remaining requests in current window
- `X-RateLimit-Reset`: Time when the rate limit resets (Unix timestamp)

### Rate Limit Handling

```python
import time
import requests

def make_rate_limited_request(url, headers, data=None, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(url, headers=headers, json=data) if data else requests.get(url, headers=headers)
            
            if response.status_code == 429:
                # Rate limited - check reset time
                reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                current_time = int(time.time())
                wait_time = max(reset_time - current_time, 1)
                
                print(f"Rate limited. Waiting {wait_time} seconds...")
                time.sleep(wait_time)
                continue
            
            return response
        
        except requests.exceptions.RequestException as e:
            if attempt == max_retries - 1:
                raise e
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise Exception("Max retries exceeded")
```

## Best Practices

### 1. Authentication Management

- Store tokens securely (use environment variables or secure storage)
- Implement token refresh logic
- Handle authentication errors gracefully

```python
import os
from datetime import datetime, timedelta

class TokenManager:
    def __init__(self):
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
    
    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return datetime.now() >= self.token_expires_at
    
    def refresh_access_token(self):
        if not self.refresh_token:
            raise Exception("No refresh token available")
        
        # Implement token refresh logic
        # ...
        
    def get_valid_token(self):
        if self.is_token_expired():
            self.refresh_access_token()
        return self.access_token
```

### 2. Pagination Handling

```python
def get_all_leads(client, filters=None):
    all_leads = []
    page = 1
    
    while True:
        params = {'page': page, 'per_page': 100}
        if filters:
            params.update(filters)
        
        response = client.get('/crm/leads', params=params)
        data = response.json()
        
        all_leads.extend(data['data'])
        
        if not data['pagination']['has_next']:
            break
        
        page += 1
    
    return all_leads
```

### 3. Bulk Operations

```python
def bulk_create_leads(client, leads_data, batch_size=10):
    results = []
    
    for i in range(0, len(leads_data), batch_size):
        batch = leads_data[i:i + batch_size]
        batch_results = []
        
        for lead_data in batch:
            try:
                result = client.post('/crm/leads', json=lead_data)
                batch_results.append({'status': 'success', 'data': result.json()})
            except Exception as e:
                batch_results.append({'status': 'error', 'error': str(e), 'data': lead_data})
        
        results.extend(batch_results)
        
        # Add delay between batches to respect rate limits
        time.sleep(1)
    
    return results
```

### 4. Webhook Verification

```python
import hmac
import hashlib

def verify_webhook_signature(payload, signature, secret):
    """Verify webhook signature for security."""
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)

# Flask webhook handler example
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhook/ai-secretary', methods=['POST'])
def handle_webhook():
    signature = request.headers.get('X-Webhook-Signature')
    payload = request.get_data(as_text=True)
    
    if not verify_webhook_signature(payload, signature, os.environ['WEBHOOK_SECRET']):
        return jsonify({'error': 'Invalid signature'}), 401
    
    event_data = request.get_json()
    
    # Process webhook event
    if event_data['type'] == 'lead.created':
        handle_lead_created(event_data['data'])
    elif event_data['type'] == 'message.received':
        handle_message_received(event_data['data'])
    
    return jsonify({'status': 'success'})
```

### 5. Monitoring and Logging

```python
import logging
import time

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class APIClient:
    def __init__(self, base_url, access_token):
        self.base_url = base_url
        self.access_token = access_token
    
    def make_request(self, method, endpoint, **kwargs):
        url = f"{self.base_url}{endpoint}"
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        
        start_time = time.time()
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            duration = time.time() - start_time
            
            logger.info(f"{method} {endpoint} - {response.status_code} - {duration:.3f}s")
            
            if response.status_code >= 400:
                logger.error(f"API Error: {response.text}")
            
            return response
        
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{method} {endpoint} - Error: {str(e)} - {duration:.3f}s")
            raise
```

This integration guide provides a comprehensive foundation for working with the AI Secretary SaaS API. For more specific use cases or advanced integrations, please refer to the full API documentation or contact our support team.