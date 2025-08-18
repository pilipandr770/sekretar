# Developer Onboarding Guide

Welcome to the AI Secretary SaaS API! This guide will help you get started with integrating our platform into your applications.

## Table of Contents

1. [Overview](#overview)
2. [Getting Started](#getting-started)
3. [Development Environment Setup](#development-environment-setup)
4. [Your First API Call](#your-first-api-call)
5. [Common Use Cases](#common-use-cases)
6. [Testing and Debugging](#testing-and-debugging)
7. [Production Deployment](#production-deployment)
8. [Support and Resources](#support-and-resources)

## Overview

The AI Secretary SaaS API is a comprehensive platform that provides:

- **Multi-channel Communication**: Handle messages from Telegram, Signal, and web widgets
- **AI-Powered Responses**: Automated customer support with OpenAI integration
- **CRM Management**: Lead tracking, pipeline management, and customer data
- **Calendar Integration**: Google Calendar sync and appointment booking
- **Knowledge Base**: RAG-powered document search and AI responses
- **Billing Integration**: Stripe-powered subscription and invoice management
- **KYB Monitoring**: Counterparty compliance and risk assessment
- **Multi-tenant Architecture**: Secure data isolation and role-based access

## Getting Started

### 1. Create Your Account

1. Visit [AI Secretary SaaS](https://ai-secretary.com)
2. Sign up for a developer account
3. Complete email verification
4. Set up your organization (tenant)

### 2. Get API Credentials

1. Log into your dashboard
2. Navigate to **Settings** → **API Keys**
3. Generate a new API key
4. Copy and securely store your credentials

### 3. Choose Your Environment

- **Sandbox**: `https://staging-api.ai-secretary.com/api/v1`
- **Production**: `https://api.ai-secretary.com/api/v1`

## Development Environment Setup

### Prerequisites

- Programming language of choice (Python, JavaScript, PHP, etc.)
- HTTP client library (requests, axios, curl, etc.)
- Text editor or IDE
- Git for version control

### Environment Variables

Create a `.env` file in your project:

```bash
# AI Secretary API Configuration
AI_SECRETARY_API_URL=https://staging-api.ai-secretary.com/api/v1
AI_SECRETARY_EMAIL=your-email@example.com
AI_SECRETARY_PASSWORD=your-secure-password

# Optional: Direct API token (if you have one)
AI_SECRETARY_ACCESS_TOKEN=your-jwt-token

# Your application settings
APP_ENV=development
DEBUG=true
```

### Install Dependencies

#### Python
```bash
pip install requests python-dotenv
```

#### Node.js
```bash
npm install axios dotenv
```

#### PHP
```bash
composer require guzzlehttp/guzzle vlucas/phpdotenv
```

## Your First API Call

Let's start with a simple health check and authentication:

### Step 1: Check API Health

```python
import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv('AI_SECRETARY_API_URL')

# Check if API is healthy
response = requests.get(f"{API_URL}/health")
print(f"API Health: {response.json()}")
```

### Step 2: Authenticate

```python
def authenticate():
    login_data = {
        'email': os.getenv('AI_SECRETARY_EMAIL'),
        'password': os.getenv('AI_SECRETARY_PASSWORD')
    }
    
    response = requests.post(f"{API_URL}/auth/login", json=login_data)
    
    if response.status_code == 200:
        tokens = response.json()
        return tokens['access_token']
    else:
        raise Exception(f"Authentication failed: {response.text}")

# Get access token
access_token = authenticate()
print(f"Authenticated successfully!")
```

### Step 3: Make Your First Authenticated Request

```python
def get_leads(access_token):
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    response = requests.get(f"{API_URL}/crm/leads", headers=headers)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Failed to get leads: {response.text}")

# Get leads
leads_data = get_leads(access_token)
print(f"Found {len(leads_data['data'])} leads")
```

### Complete Example

```python
import requests
import os
from dotenv import load_dotenv

class AISecretaryClient:
    def __init__(self):
        load_dotenv()
        self.api_url = os.getenv('AI_SECRETARY_API_URL')
        self.access_token = None
        self.headers = {'Content-Type': 'application/json'}
    
    def authenticate(self):
        """Authenticate and get access token."""
        login_data = {
            'email': os.getenv('AI_SECRETARY_EMAIL'),
            'password': os.getenv('AI_SECRETARY_PASSWORD')
        }
        
        response = requests.post(f"{self.api_url}/auth/login", json=login_data)
        
        if response.status_code == 200:
            tokens = response.json()
            self.access_token = tokens['access_token']
            self.headers['Authorization'] = f'Bearer {self.access_token}'
            return True
        else:
            raise Exception(f"Authentication failed: {response.text}")
    
    def get(self, endpoint):
        """Make GET request."""
        response = requests.get(f"{self.api_url}{endpoint}", headers=self.headers)
        return self._handle_response(response)
    
    def post(self, endpoint, data):
        """Make POST request."""
        response = requests.post(f"{self.api_url}{endpoint}", headers=self.headers, json=data)
        return self._handle_response(response)
    
    def _handle_response(self, response):
        """Handle API response."""
        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 401:
            raise Exception("Authentication failed. Please check your credentials.")
        elif response.status_code == 403:
            raise Exception("Insufficient permissions.")
        elif response.status_code == 404:
            raise Exception("Resource not found.")
        else:
            raise Exception(f"API Error: {response.text}")

# Usage
if __name__ == "__main__":
    client = AISecretaryClient()
    
    # Authenticate
    client.authenticate()
    print("✅ Authentication successful!")
    
    # Check API health
    health = client.get("/health")
    print(f"✅ API Status: {health['status']}")
    
    # Get leads
    leads = client.get("/crm/leads")
    print(f"✅ Found {len(leads['data'])} leads")
    
    # Create a test lead
    new_lead = {
        'contact': {
            'name': 'Test Prospect',
            'email': 'test@example.com',
            'phone': '+1234567890'
        },
        'source': 'api_test',
        'value': 1000
    }
    
    created_lead = client.post("/crm/leads", new_lead)
    print(f"✅ Created lead with ID: {created_lead['data']['id']}")
```

## Common Use Cases

### 1. Customer Inquiry Processing

```python
def process_customer_inquiry(client, customer_email, message):
    """Process incoming customer inquiry."""
    
    # Create inbox message
    message_data = {
        'content': message,
        'channel': 'web_widget',
        'customer_email': customer_email,
        'customer_name': customer_email.split('@')[0].title()
    }
    
    # Send message to inbox
    inbox_message = client.post('/inbox/messages', message_data)
    print(f"Message created: {inbox_message['data']['id']}")
    
    # Check if lead was auto-created
    leads = client.get(f'/crm/leads?contact_email={customer_email}')
    
    if leads['data']:
        print(f"Existing lead found: {leads['data'][0]['id']}")
        return leads['data'][0]
    else:
        # Create new lead
        lead_data = {
            'contact': {
                'name': customer_email.split('@')[0].title(),
                'email': customer_email
            },
            'source': 'customer_inquiry',
            'value': 0
        }
        
        new_lead = client.post('/crm/leads', lead_data)
        print(f"New lead created: {new_lead['data']['id']}")
        return new_lead['data']

# Usage
lead = process_customer_inquiry(
    client, 
    'prospect@example.com', 
    'Hi, I\'m interested in your AI secretary services.'
)
```

### 2. Knowledge Base Management

```python
def upload_knowledge_document(client, title, content):
    """Upload document to knowledge base."""
    
    document_data = {
        'title': title,
        'content': content,
        'type': 'text'
    }
    
    document = client.post('/knowledge/documents', document_data)
    print(f"Document uploaded: {document['data']['id']}")
    
    return document['data']

def search_knowledge_base(client, query):
    """Search knowledge base."""
    
    search_data = {
        'query': query,
        'limit': 5,
        'min_similarity': 0.7
    }
    
    results = client.post('/knowledge/search', search_data)
    
    print(f"Found {len(results['data'])} results for: {query}")
    for result in results['data']:
        print(f"- {result['content'][:100]}... (similarity: {result['similarity']:.2f})")
    
    return results['data']

# Usage
upload_knowledge_document(
    client,
    'Product Features',
    'Our AI secretary supports multiple channels including Telegram, Signal, and web widgets...'
)

search_results = search_knowledge_base(client, 'What channels do you support?')
```

### 3. Calendar Integration

```python
def book_appointment(client, lead_id, title, start_time, end_time, attendee_email):
    """Book calendar appointment for lead."""
    
    event_data = {
        'title': title,
        'description': f'Meeting scheduled via API',
        'start_time': start_time,
        'end_time': end_time,
        'attendee_email': attendee_email,
        'lead_id': lead_id
    }
    
    event = client.post('/calendar/events', event_data)
    print(f"Appointment booked: {event['data']['id']}")
    
    return event['data']

# Usage
appointment = book_appointment(
    client,
    lead_id=123,
    title='Product Demo',
    start_time='2025-08-20T10:00:00Z',
    end_time='2025-08-20T11:00:00Z',
    attendee_email='prospect@example.com'
)
```

## Testing and Debugging

### 1. API Testing with Postman

Download our Postman collection:

```bash
curl -o ai-secretary-api.postman_collection.json \
  https://api.ai-secretary.com/docs/postman-collection.json
```

Import into Postman and set up environment variables:
- `base_url`: Your API base URL
- `access_token`: Your JWT token

### 2. Unit Testing

```python
import unittest
from unittest.mock import patch, MagicMock

class TestAISecretaryClient(unittest.TestCase):
    def setUp(self):
        self.client = AISecretaryClient()
        self.client.access_token = 'test-token'
        self.client.headers['Authorization'] = 'Bearer test-token'
    
    @patch('requests.get')
    def test_get_leads(self, mock_get):
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [{'id': 1, 'name': 'Test Lead'}],
            'pagination': {'total': 1}
        }
        mock_get.return_value = mock_response
        
        # Test
        result = self.client.get('/crm/leads')
        
        # Assertions
        self.assertEqual(len(result['data']), 1)
        self.assertEqual(result['data'][0]['name'], 'Test Lead')
        mock_get.assert_called_once()
    
    @patch('requests.post')
    def test_create_lead(self, mock_post):
        # Mock response
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            'data': {'id': 123, 'name': 'New Lead'}
        }
        mock_post.return_value = mock_response
        
        # Test data
        lead_data = {
            'contact': {'name': 'Test', 'email': 'test@example.com'},
            'source': 'test'
        }
        
        # Test
        result = self.client.post('/crm/leads', lead_data)
        
        # Assertions
        self.assertEqual(result['data']['id'], 123)
        mock_post.assert_called_once()

if __name__ == '__main__':
    unittest.main()
```

### 3. Debugging Tips

```python
import logging

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class DebugAISecretaryClient(AISecretaryClient):
    def _handle_response(self, response):
        """Enhanced response handling with debugging."""
        
        # Log request details
        logger.debug(f"Request: {response.request.method} {response.request.url}")
        logger.debug(f"Request Headers: {dict(response.request.headers)}")
        if response.request.body:
            logger.debug(f"Request Body: {response.request.body}")
        
        # Log response details
        logger.debug(f"Response Status: {response.status_code}")
        logger.debug(f"Response Headers: {dict(response.headers)}")
        logger.debug(f"Response Body: {response.text}")
        
        return super()._handle_response(response)
```

## Production Deployment

### 1. Security Checklist

- [ ] Use HTTPS for all API calls
- [ ] Store API credentials securely (environment variables, secrets manager)
- [ ] Implement token refresh logic
- [ ] Add request timeout handling
- [ ] Implement rate limiting on your side
- [ ] Add proper error logging
- [ ] Validate all input data
- [ ] Use webhook signature verification

### 2. Performance Optimization

```python
import time
from functools import wraps

def retry_on_failure(max_retries=3, delay=1):
    """Decorator for retrying failed API calls."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    time.sleep(delay * (2 ** attempt))  # Exponential backoff
            return None
        return wrapper
    return decorator

class ProductionAISecretaryClient(AISecretaryClient):
    @retry_on_failure(max_retries=3)
    def get(self, endpoint):
        return super().get(endpoint)
    
    @retry_on_failure(max_retries=3)
    def post(self, endpoint, data):
        return super().post(endpoint, data)
```

### 3. Monitoring and Alerting

```python
import time
import logging
from datetime import datetime

class MonitoredAISecretaryClient(AISecretaryClient):
    def __init__(self):
        super().__init__()
        self.metrics = {
            'requests_total': 0,
            'requests_failed': 0,
            'avg_response_time': 0
        }
    
    def _handle_response(self, response):
        """Track metrics and performance."""
        self.metrics['requests_total'] += 1
        
        if response.status_code >= 400:
            self.metrics['requests_failed'] += 1
            logging.error(f"API Error: {response.status_code} - {response.text}")
        
        # Track response time
        if hasattr(response, 'elapsed'):
            response_time = response.elapsed.total_seconds()
            self.metrics['avg_response_time'] = (
                (self.metrics['avg_response_time'] * (self.metrics['requests_total'] - 1) + response_time) 
                / self.metrics['requests_total']
            )
        
        return super()._handle_response(response)
    
    def get_metrics(self):
        """Get performance metrics."""
        return {
            **self.metrics,
            'error_rate': self.metrics['requests_failed'] / max(self.metrics['requests_total'], 1),
            'timestamp': datetime.now().isoformat()
        }
```

## Support and Resources

### Documentation
- [API Reference](./openapi.yaml) - Complete OpenAPI specification
- [Integration Guide](./API_INTEGRATION_GUIDE.md) - Detailed integration examples
- [Interactive Docs](./api-docs.html) - Try the API in your browser

### Code Examples
- [Python SDK](https://github.com/ai-secretary/python-sdk)
- [JavaScript SDK](https://github.com/ai-secretary/javascript-sdk)
- [PHP SDK](https://github.com/ai-secretary/php-sdk)

### Community
- [Developer Forum](https://community.ai-secretary.com)
- [Stack Overflow](https://stackoverflow.com/questions/tagged/ai-secretary)
- [GitHub Discussions](https://github.com/ai-secretary/api-docs/discussions)

### Support Channels
- **Email**: [api-support@ai-secretary.com](mailto:api-support@ai-secretary.com)
- **Chat**: Available in your dashboard
- **Phone**: +1-555-AI-SECRETARY (business hours)

### Status and Updates
- [Status Page](https://status.ai-secretary.com)
- [API Changelog](https://changelog.ai-secretary.com)
- [Developer Newsletter](https://ai-secretary.com/newsletter)

## Next Steps

1. **Complete the Quick Start**: Follow the examples above to make your first API calls
2. **Explore Use Cases**: Review the integration guide for your specific needs
3. **Join the Community**: Connect with other developers in our forum
4. **Build Something Awesome**: Start integrating AI Secretary into your application!

Need help? Don't hesitate to reach out to our support team. We're here to help you succeed! 🚀