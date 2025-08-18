# AI Secretary SaaS API - Integration Guide

This comprehensive guide covers everything you need to know to successfully integrate with the AI Secretary SaaS API.

## Quick Start

### 1. Get API Access
1. Register your organization at `/api/v1/auth/register`
2. Verify your email and complete setup
3. Get your API credentials from the dashboard

### 2. Authentication Flow
```javascript
// 1. Login to get tokens
const loginResponse = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});

const { access_token, refresh_token } = loginResponse.data;

// 2. Use access token for API calls
const apiResponse = await fetch('/api/v1/tenant', {
  headers: { 'Authorization': `Bearer ${access_token}` }
});

// 3. Refresh token when needed
const refreshResponse = await fetch('/api/v1/auth/refresh', {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${refresh_token}` }
});
```

### 3. Make Your First API Call
```bash
curl -X GET https://api.ai-secretary.com/api/v1/health
```

## Core Concepts

### Multi-Tenancy
- Each organization is a separate tenant
- Data is completely isolated between tenants
- All API calls are automatically scoped to your tenant

### Role-Based Access Control
- **Owner**: Full access to all features
- **Manager**: Manage users, CRM, most features
- **Support**: Access inbox, CRM, knowledge base
- **Accounting**: Access billing and reports
- **Read-only**: View-only access

### Rate Limiting
- **Authenticated**: 1000 requests/hour
- **Unauthenticated**: 100 requests/hour
- **Webhooks**: 10000 requests/hour

## API Reference

### Base URLs
- **Production**: `https://api.ai-secretary.com/api/v1`
- **Staging**: `https://staging-api.ai-secretary.com/api/v1`
- **Development**: `http://localhost:5000/api/v1`

### Response Format
All responses follow this structure:
```json
{
  "success": true,
  "message": "Operation completed successfully",
  "data": { /* response data */ },
  "pagination": { /* pagination info for lists */ }
}
```

### Error Format
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "details": { /* field-specific errors */ },
    "request_id": "req_123456789"
  }
}
```

## Integration Patterns

### 1. CRM Integration
```javascript
// Sync leads from your CRM
const syncLeads = async (crmLeads) => {
  for (const crmLead of crmLeads) {
    const leadData = {
      contact: {
        name: crmLead.name,
        email: crmLead.email,
        phone: crmLead.phone,
        company: crmLead.company
      },
      source: 'crm_sync',
      value: crmLead.value,
      external_id: crmLead.id
    };
    
    await apiClient.post('/crm/leads', leadData);
  }
};
```

### 2. Webhook Integration
```javascript
// Express.js webhook handler
app.post('/webhooks/ai-secretary', (req, res) => {
  const event = req.body;
  
  switch (event.type) {
    case 'lead.created':
      // Sync to your CRM
      syncToCRM(event.data);
      break;
    case 'message.received':
      // Notify your team
      notifyTeam(event.data);
      break;
  }
  
  res.status(200).send('OK');
});
```

### 3. Knowledge Base Sync
```javascript
// Sync documentation to knowledge base
const syncDocumentation = async (docs) => {
  for (const doc of docs) {
    if (doc.type === 'url') {
      await apiClient.post('/knowledge/sources', {
        type: 'url',
        url: doc.url,
        title: doc.title
      });
    } else if (doc.type === 'file') {
      const formData = new FormData();
      formData.append('file', doc.file);
      formData.append('title', doc.title);
      
      await apiClient.post('/knowledge/documents', formData);
    }
  }
};
```

## Best Practices

### 1. Error Handling
```javascript
class APIClient {
  async makeRequest(method, endpoint, data) {
    try {
      const response = await fetch(`${this.baseURL}${endpoint}`, {
        method,
        headers: this.getHeaders(),
        body: data ? JSON.stringify(data) : null
      });
      
      if (response.status === 401) {
        await this.refreshToken();
        return this.makeRequest(method, endpoint, data);
      }
      
      if (response.status === 429) {
        const retryAfter = response.headers.get('Retry-After');
        await this.sleep(retryAfter * 1000);
        return this.makeRequest(method, endpoint, data);
      }
      
      if (!response.ok) {
        const error = await response.json();
        throw new APIError(error);
      }
      
      return response.json();
    } catch (error) {
      console.error('API request failed:', error);
      throw error;
    }
  }
}
```

### 2. Caching Strategy
```javascript
class CachedAPIClient {
  constructor(apiClient) {
    this.api = apiClient;
    this.cache = new Map();
    this.cacheTTL = 5 * 60 * 1000; // 5 minutes
  }
  
  async get(endpoint, options = {}) {
    const cacheKey = `GET:${endpoint}`;
    
    if (!options.skipCache) {
      const cached = this.cache.get(cacheKey);
      if (cached && Date.now() - cached.timestamp < this.cacheTTL) {
        return cached.data;
      }
    }
    
    const data = await this.api.get(endpoint);
    
    if (!options.skipCache) {
      this.cache.set(cacheKey, {
        data,
        timestamp: Date.now()
      });
    }
    
    return data;
  }
}
```

### 3. Batch Operations
```javascript
// Process items in batches to avoid rate limits
const processBatch = async (items, batchSize = 10) => {
  const results = [];
  
  for (let i = 0; i < items.length; i += batchSize) {
    const batch = items.slice(i, i + batchSize);
    const batchPromises = batch.map(item => processItem(item));
    
    const batchResults = await Promise.allSettled(batchPromises);
    results.push(...batchResults);
    
    // Rate limiting delay
    if (i + batchSize < items.length) {
      await sleep(1000);
    }
  }
  
  return results;
};
```

## Security Considerations

### 1. Token Storage
```javascript
// Secure token storage
class SecureTokenStorage {
  setTokens(accessToken, refreshToken) {
    // Use secure storage in production
    if (typeof window !== 'undefined') {
      // Browser - use secure cookies or encrypted localStorage
      this.setSecureCookie('access_token', accessToken);
      this.setSecureCookie('refresh_token', refreshToken);
    } else {
      // Node.js - use environment variables or secure vault
      process.env.ACCESS_TOKEN = accessToken;
      process.env.REFRESH_TOKEN = refreshToken;
    }
  }
  
  setSecureCookie(name, value) {
    document.cookie = `${name}=${value}; Secure; HttpOnly; SameSite=Strict`;
  }
}
```

### 2. Input Validation
```javascript
const validateLeadData = (data) => {
  const errors = {};
  
  if (!data.contact?.email || !isValidEmail(data.contact.email)) {
    errors.email = 'Valid email is required';
  }
  
  if (!data.contact?.name || data.contact.name.length < 2) {
    errors.name = 'Name must be at least 2 characters';
  }
  
  if (data.value && (typeof data.value !== 'number' || data.value < 0)) {
    errors.value = 'Value must be a positive number';
  }
  
  return Object.keys(errors).length > 0 ? errors : null;
};
```

### 3. Webhook Security
```javascript
const crypto = require('crypto');

const verifyWebhookSignature = (payload, signature, secret) => {
  const expectedSignature = crypto
    .createHmac('sha256', secret)
    .update(payload)
    .digest('hex');
    
  return signature === `sha256=${expectedSignature}`;
};

app.post('/webhooks/ai-secretary', (req, res) => {
  const signature = req.headers['x-signature'];
  
  if (!verifyWebhookSignature(req.body, signature, process.env.WEBHOOK_SECRET)) {
    return res.status(401).send('Invalid signature');
  }
  
  // Process webhook...
});
```

## Testing

### 1. Unit Tests
```javascript
describe('API Client', () => {
  let apiClient;
  
  beforeEach(() => {
    apiClient = new APIClient('http://localhost:5000/api/v1');
    apiClient.setToken('test-token');
  });
  
  test('should create lead successfully', async () => {
    const leadData = {
      contact: { name: 'Test Lead', email: 'test@example.com' },
      source: 'test'
    };
    
    const mockResponse = { success: true, data: { id: 123 } };
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    });
    
    const result = await apiClient.post('/crm/leads', leadData);
    
    expect(result.success).toBe(true);
    expect(result.data.id).toBe(123);
  });
});
```

### 2. Integration Tests
```javascript
describe('API Integration', () => {
  let apiClient;
  
  beforeAll(async () => {
    apiClient = new APIClient(process.env.TEST_API_URL);
    await apiClient.login(process.env.TEST_EMAIL, process.env.TEST_PASSWORD);
  });
  
  test('should complete full lead workflow', async () => {
    // Create lead
    const lead = await apiClient.post('/crm/leads', testLeadData);
    expect(lead.success).toBe(true);
    
    // Update lead
    const updated = await apiClient.put(`/crm/leads/${lead.data.id}`, {
      status: 'qualified'
    });
    expect(updated.data.status).toBe('qualified');
    
    // Create task for lead
    const task = await apiClient.post('/crm/tasks', {
      lead_id: lead.data.id,
      title: 'Follow up call'
    });
    expect(task.success).toBe(true);
  });
});
```

## Monitoring and Observability

### 1. Request Logging
```javascript
class LoggingAPIClient {
  async makeRequest(method, endpoint, data) {
    const requestId = generateRequestId();
    const startTime = Date.now();
    
    console.log(`[${requestId}] ${method} ${endpoint} - Request started`);
    
    try {
      const response = await this.api.makeRequest(method, endpoint, data);
      const duration = Date.now() - startTime;
      
      console.log(`[${requestId}] ${method} ${endpoint} - Success (${duration}ms)`);
      return response;
    } catch (error) {
      const duration = Date.now() - startTime;
      
      console.error(`[${requestId}] ${method} ${endpoint} - Error (${duration}ms):`, error);
      throw error;
    }
  }
}
```

### 2. Metrics Collection
```javascript
class MetricsCollector {
  constructor() {
    this.metrics = {
      requests: 0,
      errors: 0,
      responseTime: []
    };
  }
  
  recordRequest(duration, success) {
    this.metrics.requests++;
    this.metrics.responseTime.push(duration);
    
    if (!success) {
      this.metrics.errors++;
    }
  }
  
  getMetrics() {
    const avgResponseTime = this.metrics.responseTime.reduce((a, b) => a + b, 0) / 
                           this.metrics.responseTime.length;
    
    return {
      totalRequests: this.metrics.requests,
      errorRate: this.metrics.errors / this.metrics.requests,
      avgResponseTime: avgResponseTime
    };
  }
}
```

## Deployment

### 1. Environment Configuration
```javascript
// config.js
const config = {
  development: {
    apiUrl: 'http://localhost:5000/api/v1',
    logLevel: 'debug'
  },
  staging: {
    apiUrl: 'https://staging-api.ai-secretary.com/api/v1',
    logLevel: 'info'
  },
  production: {
    apiUrl: 'https://api.ai-secretary.com/api/v1',
    logLevel: 'error'
  }
};

module.exports = config[process.env.NODE_ENV || 'development'];
```

### 2. Health Checks
```javascript
// Health check endpoint for your integration
app.get('/health', async (req, res) => {
  try {
    // Check API connectivity
    const healthResponse = await apiClient.get('/health');
    
    if (healthResponse.status === 'healthy') {
      res.status(200).json({ status: 'healthy', api: 'connected' });
    } else {
      res.status(503).json({ status: 'unhealthy', api: 'degraded' });
    }
  } catch (error) {
    res.status(503).json({ status: 'unhealthy', api: 'disconnected' });
  }
});
```

## Troubleshooting

### Common Issues

1. **401 Unauthorized**
   - Check token expiration
   - Verify token format
   - Ensure proper Authorization header

2. **429 Rate Limited**
   - Implement exponential backoff
   - Check rate limit headers
   - Consider caching responses

3. **Validation Errors**
   - Validate data before sending
   - Check required fields
   - Verify data types and formats

### Debug Mode
```javascript
const apiClient = new APIClient(config.apiUrl, {
  debug: process.env.NODE_ENV === 'development',
  timeout: 30000,
  retries: 3
});
```

## Support

- **Documentation**: [API Reference](https://api.ai-secretary.com/api/v1/docs/swagger)
- **Examples**: [Usage Examples](https://api.ai-secretary.com/api/v1/docs/examples)
- **Support**: [api-support@ai-secretary.com](mailto:api-support@ai-secretary.com)
- **Status**: [https://status.ai-secretary.com](https://status.ai-secretary.com)

## Changelog

### v1.0.0 (Current)
- Initial API release
- Full CRM functionality
- Multi-channel messaging
- Knowledge base with RAG
- KYB monitoring
- Stripe billing integration

For the latest updates and changes, check our [API changelog](https://api.ai-secretary.com/api/v1/docs/changelog).