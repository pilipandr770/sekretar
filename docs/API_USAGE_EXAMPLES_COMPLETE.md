# AI Secretary SaaS API - Usage Examples

This document provides comprehensive examples for integrating with the AI Secretary SaaS API across all major features and use cases.

## Table of Contents

1. [Authentication Examples](#authentication-examples)
2. [Tenant Management](#tenant-management)
3. [CRM Integration](#crm-integration)
4. [Inbox Management](#inbox-management)
5. [Calendar Integration](#calendar-integration)
6. [Knowledge Base](#knowledge-base)
7. [Billing and Invoicing](#billing-and-invoicing)
8. [KYB Monitoring](#kyb-monitoring)
9. [Channel Management](#channel-management)
10. [Webhooks](#webhooks)
11. [Error Handling](#error-handling)
12. [Advanced Patterns](#advanced-patterns)

## Authentication Examples

### Register New Organization

```bash
curl -X POST https://api.ai-secretary.com/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "owner@newcompany.com",
    "password": "SecurePass123!",
    "organization_name": "New Company Ltd",
    "first_name": "John",
    "last_name": "Owner",
    "language": "en"
  }'
```

```javascript
// JavaScript/Node.js
const registerOrganization = async (orgData) => {
  const response = await fetch('https://api.ai-secretary.com/api/v1/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(orgData)
  });
  
  const result = await response.json();
  
  if (result.success) {
    // Store tokens
    localStorage.setItem('access_token', result.data.access_token);
    localStorage.setItem('refresh_token', result.data.refresh_token);
    return result.data;
  } else {
    throw new Error(result.error.message);
  }
};
```

### Login and Token Management

```javascript
class AuthManager {
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

    const result = await response.json();
    
    if (result.success) {
      this.accessToken = result.data.access_token;
      this.refreshToken = result.data.refresh_token;
      
      localStorage.setItem('access_token', this.accessToken);
      localStorage.setItem('refresh_token', this.refreshToken);
      
      return result.data;
    }
    
    throw new Error(result.error.message);
  }

  async refreshAccessToken() {
    if (!this.refreshToken) {
      throw new Error('No refresh token available');
    }

    const response = await fetch(`${this.baseURL}/auth/refresh`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${this.refreshToken}` }
    });

    const result = await response.json();
    
    if (result.success) {
      this.accessToken = result.data.access_token;
      localStorage.setItem('access_token', this.accessToken);
      return result.data;
    }
    
    throw new Error('Failed to refresh token');
  }

  getAuthHeaders() {
    return {
      'Authorization': `Bearer ${this.accessToken}`,
      'Content-Type': 'application/json'
    };
  }
}
```

## CRM Integration

### Lead Management

```javascript
class CRMManager {
  constructor(authManager) {
    this.auth = authManager;
    this.baseURL = 'https://api.ai-secretary.com/api/v1';
  }

  async createLead(leadData) {
    const response = await fetch(`${this.baseURL}/crm/leads`, {
      method: 'POST',
      headers: this.auth.getAuthHeaders(),
      body: JSON.stringify(leadData)
    });
    
    return response.json();
  }

  async updateLead(leadId, updateData) {
    const response = await fetch(`${this.baseURL}/crm/leads/${leadId}`, {
      method: 'PUT',
      headers: this.auth.getAuthHeaders(),
      body: JSON.stringify(updateData)
    });
    
    return response.json();
  }

  async getLeads(filters = {}) {
    const params = new URLSearchParams(filters);
    const response = await fetch(`${this.baseURL}/crm/leads?${params}`, {
      headers: this.auth.getAuthHeaders()
    });
    
    return response.json();
  }
}

// Usage examples
const crm = new CRMManager(authManager);

// Create a new lead
const newLead = {
  contact: {
    name: "John Prospect",
    email: "john@prospect.com",
    phone: "+1234567890",
    company: "Prospect Corp"
  },
  source: "website",
  value: 5000,
  pipeline_id: 1,
  stage_id: 1,
  notes: "Interested in premium package"
};

const lead = await crm.createLead(newLead);
```

## Knowledge Base

### Document Management

```javascript
class KnowledgeManager {
  constructor(authManager) {
    this.auth = authManager;
    this.baseURL = 'https://api.ai-secretary.com/api/v1';
  }

  async uploadDocument(file, metadata = {}) {
    const formData = new FormData();
    formData.append('file', file);
    
    Object.keys(metadata).forEach(key => {
      formData.append(key, metadata[key]);
    });

    const response = await fetch(`${this.baseURL}/knowledge/documents`, {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${this.auth.accessToken}`
      },
      body: formData
    });

    return response.json();
  }

  async searchKnowledge(query, options = {}) {
    const searchData = {
      query,
      limit: options.limit || 10,
      include_citations: options.includeCitations !== false,
      ...options
    };

    const response = await fetch(`${this.baseURL}/knowledge/search`, {
      method: 'POST',
      headers: this.auth.getAuthHeaders(),
      body: JSON.stringify(searchData)
    });

    return response.json();
  }
}
```

## Error Handling

### Comprehensive Error Handling

```javascript
class APIError extends Error {
  constructor(response, data) {
    super(data.error?.message || 'API request failed');
    this.name = 'APIError';
    this.status = response.status;
    this.code = data.error?.code;
    this.details = data.error?.details;
    this.requestId = data.error?.request_id;
  }
}

class APIClient {
  constructor(baseURL, authManager) {
    this.baseURL = baseURL;
    this.auth = authManager;
    this.retryAttempts = 3;
    this.retryDelay = 1000;
  }

  async makeRequest(method, endpoint, body = null, options = {}) {
    const url = `${this.baseURL}${endpoint}`;
    const config = {
      method,
      headers: this.auth.getAuthHeaders(),
      ...options
    };

    if (body) {
      config.body = JSON.stringify(body);
    }

    let lastError;
    
    for (let attempt = 1; attempt <= this.retryAttempts; attempt++) {
      try {
        const response = await fetch(url, config);
        const data = await response.json();

        if (!response.ok) {
          if (response.status === 401) {
            await this.auth.refreshAccessToken();
            config.headers = this.auth.getAuthHeaders();
            
            const retryResponse = await fetch(url, config);
            const retryData = await retryResponse.json();
            
            if (!retryResponse.ok) {
              throw new APIError(retryResponse, retryData);
            }
            
            return retryData;
          } else if (response.status === 429) {
            const retryAfter = response.headers.get('Retry-After');
            const delay = retryAfter ? parseInt(retryAfter) * 1000 : this.retryDelay * attempt;
            
            await this.sleep(delay);
            continue;
          }
          
          throw new APIError(response, data);
        }

        return data;
      } catch (error) {
        lastError = error;
        
        if (attempt === this.retryAttempts) {
          throw lastError;
        }
        
        const delay = this.retryDelay * Math.pow(2, attempt - 1);
        await this.sleep(delay);
      }
    }
    
    throw lastError;
  }

  sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}
```

For more comprehensive examples and advanced patterns, please refer to the complete documentation at `/api/v1/docs/swagger` or contact our support team.