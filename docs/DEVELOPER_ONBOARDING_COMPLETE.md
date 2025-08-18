# AI Secretary SaaS API - Developer Onboarding Guide

Welcome to the AI Secretary SaaS API! This comprehensive guide will help you get started with integrating our platform into your applications.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Authentication](#authentication)
3. [API Overview](#api-overview)
4. [Core Concepts](#core-concepts)
5. [Integration Examples](#integration-examples)
6. [SDKs and Tools](#sdks-and-tools)
7. [Best Practices](#best-practices)
8. [Troubleshooting](#troubleshooting)
9. [Support](#support)

## Quick Start

### 1. Get Your API Credentials

First, register your organization to get API access:

```bash
curl -X POST https://api.ai-secretary.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@company.com",
    "password": "secure-password",
    "organization_name": "Your Company",
    "first_name": "Your",
    "last_name": "Name"
  }'
```

### 2. Authenticate and Get Tokens

```bash
curl -X POST https://api.ai-secretary.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-email@company.com",
    "password": "secure-password"
  }'
```

Response:
```json
{
  "success": true,
  "data": {
    "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
    "token_type": "Bearer"
  }
}
```

### 3. Make Your First API Call

```bash
curl -X GET https://api.ai-secretary.com/api/v1/tenant \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

## Authentication

### JWT Token Flow

The API uses JWT (JSON Web Tokens) for authentication:

1. **Access Token**: Short-lived token (1 hour) for API requests
2. **Refresh Token**: Long-lived token (30 days) to get new access tokens

### Token Management

#### JavaScript Example
```javascript
class APIClient {
  constructor(baseURL) {
    this.baseURL = baseURL;
    this.accessToken = localStorage.getItem('access_token');
    this.refreshToken = localStorage.getItem('refresh_token');
  }

  async login(email, password) {
    const response = await fetch(`${this.baseURL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password })
    });
    
    const data = await response.json();
    if (data.success) {
      this.accessToken = data.data.access_token;
      this.refreshToken = data.data.refresh_token;
      localStorage.setItem('access_token', this.accessToken);
      localStorage.setItem('refresh_token', this.refreshToken);
    }
    return data;
  }

  async refreshAccessToken() {
    const response = await fetch(`${this.baseURL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.refreshToken}` }
    });
    
    const data = await response.json();
    if (data.success) {
      this.accessToken = data.data.access_token;
      localStorage.setItem('access_token', this.accessToken);
    }
    return data;
  }

  async apiCall(method, endpoint, body = null) {
    let response = await fetch(`${this.baseURL}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: body ? JSON.stringify(body) : null
    });

    // Handle token expiration
    if (response.status === 401) {
      await this.refreshAccessToken();
      response = await fetch(`${this.baseURL}${endpoint}`, {
        method,
        headers: {
          'Authorization': `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json'
        },
        body: body ? JSON.stringify(body) : null
      });
    }

    return response.json();
  }
}
```

#### Python Example
```python
import requests
import json
from datetime import datetime, timedelta

class AISecretaryAPI:
    def __init__(self, base_url):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None

    def login(self, email, password):
        response = requests.post(f"{self.base_url}/auth/login", 
                               json={"email": email, "password": password})
        data = response.json()
        
        if data.get('success'):
            self.access_token = data['data']['access_token']
            self.refresh_token = data['data']['refresh_token']
            # JWT tokens typically expire in 1 hour
            self.token_expires_at = datetime.now() + timedelta(hours=1)
        
        return data

    def refresh_access_token(self):
        headers = {'Authorization': f'Bearer {self.refresh_token}'}
        response = requests.post(f"{self.base_url}/auth/refresh", headers=headers)
        data = response.json()
        
        if data.get('success'):
            self.access_token = data['data']['access_token']
            self.token_expires_at = datetime.now() + timedelta(hours=1)
        
        return data

    def make_request(self, method, endpoint, **kwargs):
        # Check if token needs refresh
        if self.token_expires_at and datetime.now() >= self.token_expires_at:
            self.refresh_access_token()

        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        kwargs['headers'] = headers

        response = requests.request(method, f"{self.base_url}{endpoint}", **kwargs)
        
        # Handle 401 (token expired)
        if response.status_code == 401:
            self.refresh_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.request(method, f"{self.base_url}{endpoint}", **kwargs)

        return response

    # Convenience methods
    def get(self, endpoint, **kwargs):
        return self.make_request('GET', endpoint, **kwargs)

    def post(self, endpoint, **kwargs):
        return self.make_request('POST', endpoint, **kwargs)

    def put(self, endpoint, **kwargs):
        return self.make_request('PUT', endpoint, **kwargs)

    def delete(self, endpoint, **kwargs):
        return self.make_request('DELETE', endpoint, **kwargs)
```

## API Overview

### Base URLs
- **Production**: `https://api.ai-secretary.com/api/v1`
- **Staging**: `https://staging-api.ai-secretary.com/api/v1`
- **Development**: `http://localhost:5000/api/v1`

### Core Endpoints

| Category | Endpoint | Description |
|----------|----------|-------------|
| **System** | `/health` | System health check |
| **Auth** | `/auth/*` | Authentication and user management |
| **Tenant** | `/tenant/*` | Organization and user management |
| **Inbox** | `/inbox/*` | Message and conversation management |
| **CRM** | `/crm/*` | Lead and customer management |
| **Calendar** | `/calendar/*` | Calendar integration and booking |
| **Knowledge** | `/knowledge/*` | Document and knowledge base |
| **Billing** | `/billing/*` | Invoicing and subscriptions |
| **KYB** | `/kyb/*` | Know Your Business monitoring |
| **Channels** | `/channels/*` | Communication channel setup |

### Response Format

All API responses follow a consistent format:

**Success Response:**
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": {
    // Response data here
  },
  "pagination": {  // Only for paginated endpoints
    "page": 1,
    "per_page": 20,
    "total": 100,
    "pages": 5
  }
}
```

**Error Response:**
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "details": {
      "field": "Specific field error"
    },
    "request_id": "req_123456789"
  }
}
```

## Core Concepts

### Multi-Tenancy

The platform is built with multi-tenancy in mind:
- Each organization is a separate tenant
- Data is completely isolated between tenants
- Users belong to a single tenant
- API calls are automatically scoped to the authenticated user's tenant

### Role-Based Access Control (RBAC)

Users have different roles with specific permissions:

| Role | Permissions |
|------|-------------|
| **Owner** | Full access to all features and settings |
| **Manager** | Manage users, CRM, and most features |
| **Support** | Access inbox, CRM, and knowledge base |
| **Accounting** | Access billing, invoices, and reports |
| **Read-only** | View-only access to most features |

### AI Agent System

The platform uses specialized AI agents:
- **Router Agent**: Detects intent and routes messages
- **Supervisor Agent**: Filters content and ensures compliance
- **Specialized Agents**: Sales, Support, Billing, Operations

### Communication Channels

Supported channels:
- **Telegram Bot**: Real-time messaging via Telegram
- **Signal**: Secure messaging via Signal
- **Web Widget**: Embeddable chat widget for websites
- **Email**: Traditional email integration (coming soon)

## Integration Examples

### 1. CRM Integration

#### Create a Lead
```javascript
const api = new APIClient('https://api.ai-secretary.com/api/v1');

// Create a new lead
const leadData = {
  contact: {
    name: "John Prospect",
    email: "john@prospect.com",
    phone: "+1234567890",
    company: "Prospect Corp"
  },
  source: "website",
  value: 5000,
  notes: "Interested in our premium package"
};

const result = await api.apiCall('POST', '/crm/leads', leadData);
console.log('Lead created:', result.data);
```

#### Update Lead Status
```javascript
const leadId = 123;
const updateData = {
  status: "qualified",
  stage_id: 2,
  notes: "Qualified during discovery call"
};

const result = await api.apiCall('PUT', `/crm/leads/${leadId}`, updateData);
```

### 2. Inbox Management

#### List Messages
```javascript
const messages = await api.apiCall('GET', '/inbox/messages?status=new&page=1');
console.log('New messages:', messages.data);
```

#### Send Response
```javascript
const messageId = 456;
const response = {
  content: "Thank you for your inquiry. I'll get back to you shortly.",
  ai_generated: false
};

await api.apiCall('POST', `/inbox/messages/${messageId}/respond`, response);
```

### 3. Knowledge Base

#### Upload Document
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);
formData.append('title', 'Product Manual');

const response = await fetch(`${api.baseURL}/knowledge/documents`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${api.accessToken}`
  },
  body: formData
});

const result = await response.json();
```

#### Search Knowledge Base
```javascript
const searchQuery = {
  query: "How to reset password?",
  limit: 5
};

const results = await api.apiCall('POST', '/knowledge/search', searchQuery);
console.log('Search results:', results.data.results);
```

### 4. Calendar Integration

#### Connect Google Calendar
```javascript
// Redirect user to OAuth URL
const authUrl = await api.apiCall('GET', '/calendar/google/auth-url');
window.location.href = authUrl.data.auth_url;

// After OAuth callback, handle the code
const oauthCode = new URLSearchParams(window.location.search).get('code');
const tokenResult = await api.apiCall('POST', '/calendar/google/callback', {
  code: oauthCode
});
```

#### Book Appointment
```javascript
const appointmentData = {
  title: "Product Demo",
  start_time: "2024-01-20T14:00:00Z",
  end_time: "2024-01-20T15:00:00Z",
  attendee_email: "client@example.com",
  description: "Product demonstration and Q&A session"
};

const booking = await api.apiCall('POST', '/calendar/appointments', appointmentData);
```

### 5. Billing Integration

#### Create Invoice
```javascript
const invoiceData = {
  customer_email: "client@example.com",
  amount: 1500,
  currency: "USD",
  description: "Consulting services - January 2024",
  due_date: "2024-02-15"
};

const invoice = await api.apiCall('POST', '/billing/invoices', invoiceData);
console.log('Invoice created:', invoice.data.stripe_invoice_id);
```

### 6. KYB Monitoring

#### Add Counterparty
```javascript
const counterpartyData = {
  name: "Business Partner Ltd",
  vat_number: "GB123456789",
  lei_code: "213800ABCDEFGHIJKL12",
  country: "GB"
};

const counterparty = await api.apiCall('POST', '/kyb/counterparties', counterpartyData);
```

#### Get Risk Alerts
```javascript
const alerts = await api.apiCall('GET', '/kyb/alerts?severity=high&is_read=false');
console.log('High-risk alerts:', alerts.data);
```

## SDKs and Tools

### Official SDKs (Coming Soon)
- **JavaScript/Node.js SDK**: Full-featured SDK with TypeScript support
- **Python SDK**: Comprehensive Python library with async support
- **PHP SDK**: Laravel-compatible PHP package

### Development Tools

#### Postman Collection
Download our Postman collection for easy API testing:
```bash
curl -o ai-secretary-api.postman_collection.json \
  https://api.ai-secretary.com/api/v1/docs/postman
```

#### OpenAPI Specification
- **YAML**: `https://api.ai-secretary.com/api/v1/docs/openapi.yaml`
- **JSON**: `https://api.ai-secretary.com/api/v1/docs/openapi.json`

#### Interactive Documentation
- **Swagger UI**: `https://api.ai-secretary.com/api/v1/docs/swagger`
- **ReDoc**: `https://api.ai-secretary.com/api/v1/docs/redoc`

### Code Generation

Use OpenAPI generators to create client libraries:

```bash
# Generate JavaScript client
npx @openapitools/openapi-generator-cli generate \
  -i https://api.ai-secretary.com/api/v1/docs/openapi.yaml \
  -g javascript \
  -o ./ai-secretary-js-client

# Generate Python client
openapi-generator generate \
  -i https://api.ai-secretary.com/api/v1/docs/openapi.yaml \
  -g python \
  -o ./ai-secretary-python-client
```

## Best Practices

### 1. Authentication
- Store tokens securely (never in localStorage for sensitive apps)
- Implement automatic token refresh
- Handle 401 responses gracefully
- Use HTTPS in production

### 2. Error Handling
```javascript
async function handleAPICall(apiFunction) {
  try {
    const result = await apiFunction();
    return result;
  } catch (error) {
    if (error.status === 401) {
      // Handle authentication error
      await refreshToken();
      return apiFunction(); // Retry
    } else if (error.status === 429) {
      // Handle rate limiting
      const retryAfter = error.headers['Retry-After'] || 60;
      await sleep(retryAfter * 1000);
      return apiFunction(); // Retry
    } else if (error.status >= 500) {
      // Handle server errors
      console.error('Server error:', error);
      throw new Error('Service temporarily unavailable');
    } else {
      // Handle client errors
      throw error;
    }
  }
}
```

### 3. Rate Limiting
- Monitor rate limit headers
- Implement exponential backoff
- Cache responses when possible
- Use webhooks instead of polling

### 4. Data Validation
```javascript
function validateEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

function validateLeadData(leadData) {
  const errors = {};
  
  if (!leadData.contact?.name) {
    errors.name = 'Contact name is required';
  }
  
  if (!leadData.contact?.email || !validateEmail(leadData.contact.email)) {
    errors.email = 'Valid email address is required';
  }
  
  if (!leadData.source) {
    errors.source = 'Lead source is required';
  }
  
  return Object.keys(errors).length > 0 ? errors : null;
}
```

### 5. Pagination
```javascript
async function getAllLeads() {
  const allLeads = [];
  let page = 1;
  let hasMore = true;

  while (hasMore) {
    const response = await api.apiCall('GET', `/crm/leads?page=${page}&per_page=100`);
    allLeads.push(...response.data);
    
    hasMore = response.pagination.has_next;
    page++;
  }

  return allLeads;
}
```

### 6. Webhooks
```javascript
// Express.js webhook handler
app.post('/webhooks/ai-secretary', express.raw({type: 'application/json'}), (req, res) => {
  const signature = req.headers['x-signature'];
  const payload = req.body;
  
  // Verify webhook signature
  if (!verifyWebhookSignature(payload, signature)) {
    return res.status(401).send('Invalid signature');
  }
  
  const event = JSON.parse(payload);
  
  switch (event.type) {
    case 'message.received':
      handleNewMessage(event.data);
      break;
    case 'lead.created':
      handleNewLead(event.data);
      break;
    case 'invoice.paid':
      handleInvoicePaid(event.data);
      break;
    default:
      console.log('Unknown event type:', event.type);
  }
  
  res.status(200).send('OK');
});
```

## Troubleshooting

### Common Issues

#### 1. Authentication Errors (401)
```
Error: {"error": {"code": "TOKEN_EXPIRED", "message": "Access token has expired"}}
```
**Solution**: Implement automatic token refresh using the refresh token.

#### 2. Rate Limiting (429)
```
Error: {"error": {"code": "RATE_LIMIT_EXCEEDED", "message": "Too many requests"}}
```
**Solution**: Check `Retry-After` header and implement exponential backoff.

#### 3. Validation Errors (400)
```
Error: {"error": {"code": "VALIDATION_ERROR", "details": {"email": ["Invalid email format"]}}}
```
**Solution**: Validate data on the client side before sending requests.

#### 4. Tenant Access Errors (403)
```
Error: {"error": {"code": "INSUFFICIENT_PERMISSIONS", "message": "User lacks required permissions"}}
```
**Solution**: Check user role and permissions. Some operations require specific roles.

### Debug Mode

Enable debug logging in your API client:

```javascript
class APIClient {
  constructor(baseURL, debug = false) {
    this.baseURL = baseURL;
    this.debug = debug;
  }

  async apiCall(method, endpoint, body = null) {
    if (this.debug) {
      console.log(`API Call: ${method} ${endpoint}`, body);
    }

    const response = await fetch(`${this.baseURL}${endpoint}`, {
      method,
      headers: {
        'Authorization': `Bearer ${this.accessToken}`,
        'Content-Type': 'application/json'
      },
      body: body ? JSON.stringify(body) : null
    });

    const result = await response.json();

    if (this.debug) {
      console.log(`API Response: ${response.status}`, result);
    }

    return result;
  }
}
```

### Testing

#### Unit Tests Example
```javascript
// Jest test example
describe('AI Secretary API Client', () => {
  let api;

  beforeEach(() => {
    api = new APIClient('http://localhost:5000/api/v1');
    api.accessToken = 'test-token';
  });

  test('should create lead successfully', async () => {
    const leadData = {
      contact: {
        name: "Test Lead",
        email: "test@example.com"
      },
      source: "test"
    };

    // Mock fetch
    global.fetch = jest.fn().mockResolvedValue({
      json: () => Promise.resolve({
        success: true,
        data: { id: 123, ...leadData }
      })
    });

    const result = await api.apiCall('POST', '/crm/leads', leadData);
    
    expect(result.success).toBe(true);
    expect(result.data.id).toBe(123);
  });
});
```

## Support

### Documentation
- **API Reference**: [https://api.ai-secretary.com/api/v1/docs/swagger](https://api.ai-secretary.com/api/v1/docs/swagger)
- **Integration Guide**: [https://api.ai-secretary.com/api/v1/docs/integration-guide](https://api.ai-secretary.com/api/v1/docs/integration-guide)
- **Examples**: [https://api.ai-secretary.com/api/v1/docs/examples](https://api.ai-secretary.com/api/v1/docs/examples)

### Community
- **GitHub**: [https://github.com/ai-secretary/api-examples](https://github.com/ai-secretary/api-examples)
- **Discord**: [https://discord.gg/ai-secretary](https://discord.gg/ai-secretary)
- **Stack Overflow**: Tag your questions with `ai-secretary-api`

### Support Channels
- **Email**: [api-support@ai-secretary.com](mailto:api-support@ai-secretary.com)
- **Support Portal**: [https://support.ai-secretary.com](https://support.ai-secretary.com)
- **Status Page**: [https://status.ai-secretary.com](https://status.ai-secretary.com)

### SLA and Uptime
- **Uptime Target**: 99.9%
- **Response Time**: < 200ms (95th percentile)
- **Support Response**: < 24 hours for standard support

---

## Next Steps

1. **Set up your development environment** using the examples above
2. **Explore the interactive documentation** at `/docs/swagger`
3. **Join our developer community** for support and updates
4. **Build your first integration** using our comprehensive examples
5. **Subscribe to our developer newsletter** for API updates and best practices

Happy coding! 🚀