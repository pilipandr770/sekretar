"""API documentation endpoints and interactive interface."""
import os
from flask import Blueprint, render_template, jsonify, send_from_directory, current_app
from flask_babel import gettext as _
from app.utils.response import success_response, error_response
import yaml
import json

docs_bp = Blueprint('docs', __name__)


@docs_bp.route('/openapi.yaml')
def openapi_spec():
    """Serve OpenAPI specification in YAML format."""
    try:
        spec_path = os.path.join(current_app.root_path, '..', 'docs', 'openapi_complete.yaml')
        
        if not os.path.exists(spec_path):
            return error_response(
                error_code='SPEC_NOT_FOUND',
                message=_('OpenAPI specification not found'),
                status_code=404
            )
        
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_content = f.read()
        
        return spec_content, 200, {'Content-Type': 'application/x-yaml'}
        
    except Exception as e:
        return error_response(
            error_code='SPEC_READ_ERROR',
            message=_('Failed to read OpenAPI specification'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/openapi.json')
def openapi_spec_json():
    """Serve OpenAPI specification in JSON format."""
    try:
        spec_path = os.path.join(current_app.root_path, '..', 'docs', 'openapi_complete.yaml')
        
        if not os.path.exists(spec_path):
            return error_response(
                error_code='SPEC_NOT_FOUND',
                message=_('OpenAPI specification not found'),
                status_code=404
            )
        
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec_yaml = yaml.safe_load(f)
        
        return jsonify(spec_yaml)
        
    except Exception as e:
        return error_response(
            error_code='SPEC_READ_ERROR',
            message=_('Failed to read OpenAPI specification'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/swagger')
@docs_bp.route('/swagger/')
def swagger_ui():
    """Serve Swagger UI for interactive API documentation."""
    try:
        return render_template('docs/swagger.html', 
                             api_title="AI Secretary SaaS API",
                             spec_url="/api/v1/docs/openapi.json")
    except Exception as e:
        return error_response(
            error_code='SWAGGER_UI_ERROR',
            message=_('Failed to load Swagger UI'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/redoc')
@docs_bp.route('/redoc/')
def redoc_ui():
    """Serve ReDoc UI for interactive API documentation."""
    try:
        return render_template('docs/redoc.html',
                             api_title="AI Secretary SaaS API", 
                             spec_url="/api/v1/docs/openapi.json")
    except Exception as e:
        return error_response(
            error_code='REDOC_UI_ERROR',
            message=_('Failed to load ReDoc UI'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/postman')
def postman_collection():
    """Generate Postman collection from OpenAPI spec."""
    try:
        spec_path = os.path.join(current_app.root_path, '..', 'docs', 'openapi_complete.yaml')
        
        if not os.path.exists(spec_path):
            return error_response(
                error_code='SPEC_NOT_FOUND',
                message=_('OpenAPI specification not found'),
                status_code=404
            )
        
        with open(spec_path, 'r', encoding='utf-8') as f:
            spec = yaml.safe_load(f)
        
        # Convert OpenAPI spec to Postman collection format
        collection = {
            "info": {
                "name": spec.get('info', {}).get('title', 'AI Secretary API'),
                "description": spec.get('info', {}).get('description', ''),
                "version": spec.get('info', {}).get('version', '1.0.0'),
                "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
            },
            "auth": {
                "type": "bearer",
                "bearer": [
                    {
                        "key": "token",
                        "value": "{{access_token}}",
                        "type": "string"
                    }
                ]
            },
            "variable": [
                {
                    "key": "base_url",
                    "value": "http://localhost:5000/api/v1",
                    "type": "string"
                },
                {
                    "key": "access_token",
                    "value": "",
                    "type": "string"
                }
            ],
            "item": []
        }
        
        # Convert paths to Postman requests
        paths = spec.get('paths', {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method.upper() in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                    request_item = {
                        "name": details.get('summary', f"{method.upper()} {path}"),
                        "request": {
                            "method": method.upper(),
                            "header": [
                                {
                                    "key": "Content-Type",
                                    "value": "application/json",
                                    "type": "text"
                                }
                            ],
                            "url": {
                                "raw": "{{base_url}}" + path,
                                "host": ["{{base_url}}"],
                                "path": path.strip('/').split('/')
                            },
                            "description": details.get('description', '')
                        }
                    }
                    
                    # Add request body if present
                    if 'requestBody' in details:
                        request_body = details['requestBody']
                        if 'application/json' in request_body.get('content', {}):
                            schema = request_body['content']['application/json'].get('schema', {})
                            if 'example' in schema:
                                request_item['request']['body'] = {
                                    "mode": "raw",
                                    "raw": json.dumps(schema['example'], indent=2)
                                }
                    
                    collection['item'].append(request_item)
        
        return jsonify(collection), 200, {
            'Content-Type': 'application/json',
            'Content-Disposition': 'attachment; filename="ai-secretary-api.postman_collection.json"'
        }
        
    except Exception as e:
        return error_response(
            error_code='POSTMAN_GENERATION_ERROR',
            message=_('Failed to generate Postman collection'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/examples')
def api_examples():
    """Provide API usage examples and integration guides."""
    try:
        examples = {
            "authentication": {
                "title": "Authentication Examples",
                "description": "How to authenticate and manage tokens",
                "examples": [
                    {
                        "name": "Register new tenant",
                        "method": "POST",
                        "endpoint": "/auth/register",
                        "request": {
                            "email": "owner@example.com",
                            "password": "securepassword123",
                            "organization_name": "Example Corp",
                            "first_name": "John",
                            "last_name": "Doe"
                        },
                        "response": {
                            "success": True,
                            "message": "Registration successful",
                            "data": {
                                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                                "token_type": "Bearer"
                            }
                        }
                    },
                    {
                        "name": "Login",
                        "method": "POST", 
                        "endpoint": "/auth/login",
                        "request": {
                            "email": "user@example.com",
                            "password": "securepassword123"
                        },
                        "response": {
                            "success": True,
                            "message": "Login successful",
                            "data": {
                                "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                                "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
                                "token_type": "Bearer"
                            }
                        }
                    }
                ]
            },
            "crm": {
                "title": "CRM Examples",
                "description": "Managing leads, contacts, and sales pipeline",
                "examples": [
                    {
                        "name": "Create lead",
                        "method": "POST",
                        "endpoint": "/crm/leads",
                        "headers": {
                            "Authorization": "Bearer <access_token>",
                            "Content-Type": "application/json"
                        },
                        "request": {
                            "contact": {
                                "name": "John Prospect",
                                "email": "john@prospect.com",
                                "phone": "+1234567890",
                                "company": "Prospect Corp"
                            },
                            "source": "website",
                            "value": 5000,
                            "notes": "Initial inquiry about our services"
                        },
                        "response": {
                            "success": True,
                            "message": "Lead created successfully",
                            "data": {
                                "id": 123,
                                "contact": {
                                    "name": "John Prospect",
                                    "email": "john@prospect.com"
                                },
                                "status": "new",
                                "created_at": "2024-01-15T10:30:00Z"
                            }
                        }
                    }
                ]
            },
            "inbox": {
                "title": "Inbox Examples", 
                "description": "Managing messages and conversations",
                "examples": [
                    {
                        "name": "List messages",
                        "method": "GET",
                        "endpoint": "/inbox/messages?page=1&per_page=20",
                        "headers": {
                            "Authorization": "Bearer <access_token>"
                        },
                        "response": {
                            "success": True,
                            "message": "Messages retrieved successfully",
                            "data": [
                                {
                                    "id": 456,
                                    "content": "Hello, I need help with...",
                                    "channel": "telegram",
                                    "status": "new",
                                    "customer_name": "Jane Customer",
                                    "created_at": "2024-01-15T10:30:00Z"
                                }
                            ],
                            "pagination": {
                                "page": 1,
                                "per_page": 20,
                                "total": 45,
                                "pages": 3
                            }
                        }
                    }
                ]
            },
            "knowledge": {
                "title": "Knowledge Base Examples",
                "description": "Managing documents and knowledge search",
                "examples": [
                    {
                        "name": "Upload document",
                        "method": "POST",
                        "endpoint": "/knowledge/documents",
                        "headers": {
                            "Authorization": "Bearer <access_token>",
                            "Content-Type": "multipart/form-data"
                        },
                        "request": "Form data with 'file' field containing document",
                        "response": {
                            "success": True,
                            "message": "Document uploaded successfully",
                            "data": {
                                "id": 789,
                                "title": "Product Manual.pdf",
                                "status": "processing",
                                "created_at": "2024-01-15T10:30:00Z"
                            }
                        }
                    },
                    {
                        "name": "Search knowledge base",
                        "method": "POST",
                        "endpoint": "/knowledge/search",
                        "headers": {
                            "Authorization": "Bearer <access_token>",
                            "Content-Type": "application/json"
                        },
                        "request": {
                            "query": "How to reset password?",
                            "limit": 5
                        },
                        "response": {
                            "success": True,
                            "message": "Search completed successfully",
                            "data": {
                                "results": [
                                    {
                                        "content": "To reset your password, go to...",
                                        "source": "User Manual",
                                        "relevance_score": 0.95
                                    }
                                ]
                            }
                        }
                    }
                ]
            }
        }
        
        return success_response(
            message=_('API examples retrieved successfully'),
            data=examples
        )
        
    except Exception as e:
        return error_response(
            error_code='EXAMPLES_ERROR',
            message=_('Failed to load API examples'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/tester')
@docs_bp.route('/tester/')
def api_tester():
    """Interactive API testing interface."""
    try:
        return render_template('docs/api_tester.html')
    except Exception as e:
        return error_response(
            error_code='API_TESTER_ERROR',
            message=_('Failed to load API tester'),
            status_code=500,
            details=str(e)
        )


@docs_bp.route('/integration-guide')
def integration_guide():
    """Provide integration guide and best practices."""
    try:
        guide = {
            "getting_started": {
                "title": "Getting Started",
                "steps": [
                    {
                        "step": 1,
                        "title": "Register your organization",
                        "description": "Create a new tenant account using the /auth/register endpoint",
                        "endpoint": "POST /auth/register"
                    },
                    {
                        "step": 2,
                        "title": "Authenticate",
                        "description": "Login to get access tokens using the /auth/login endpoint",
                        "endpoint": "POST /auth/login"
                    },
                    {
                        "step": 3,
                        "title": "Configure your tenant",
                        "description": "Update tenant settings and add team members",
                        "endpoint": "PUT /tenant"
                    },
                    {
                        "step": 4,
                        "title": "Set up channels",
                        "description": "Configure communication channels (Telegram, Signal, Web widget)",
                        "endpoint": "POST /channels"
                    },
                    {
                        "step": 5,
                        "title": "Upload knowledge base",
                        "description": "Upload documents to train your AI assistant",
                        "endpoint": "POST /knowledge/documents"
                    }
                ]
            },
            "authentication": {
                "title": "Authentication Flow",
                "description": "How to handle JWT tokens and refresh them",
                "flow": [
                    "1. Register or login to get access_token and refresh_token",
                    "2. Include access_token in Authorization header: 'Bearer <token>'",
                    "3. When access_token expires (401 response), use refresh_token to get new access_token",
                    "4. Store tokens securely and handle token expiration gracefully"
                ],
                "code_examples": {
                    "javascript": """
// Login and store tokens
const response = await fetch('/api/v1/auth/login', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email, password })
});
const { data } = await response.json();
localStorage.setItem('access_token', data.access_token);
localStorage.setItem('refresh_token', data.refresh_token);

// Make authenticated requests
const apiCall = async (endpoint, options = {}) => {
  const token = localStorage.getItem('access_token');
  const response = await fetch(endpoint, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options.headers
    }
  });
  
  if (response.status === 401) {
    // Token expired, refresh it
    await refreshToken();
    return apiCall(endpoint, options); // Retry
  }
  
  return response;
};
                    """,
                    "python": """
import requests
import json

class APIClient:
    def __init__(self, base_url):
        self.base_url = base_url
        self.access_token = None
        self.refresh_token = None
    
    def login(self, email, password):
        response = requests.post(f"{self.base_url}/auth/login", 
                               json={"email": email, "password": password})
        data = response.json()["data"]
        self.access_token = data["access_token"]
        self.refresh_token = data["refresh_token"]
    
    def make_request(self, method, endpoint, **kwargs):
        headers = kwargs.get('headers', {})
        headers['Authorization'] = f'Bearer {self.access_token}'
        kwargs['headers'] = headers
        
        response = requests.request(method, f"{self.base_url}{endpoint}", **kwargs)
        
        if response.status_code == 401:
            self.refresh_access_token()
            headers['Authorization'] = f'Bearer {self.access_token}'
            response = requests.request(method, f"{self.base_url}{endpoint}", **kwargs)
        
        return response
                    """
                }
            },
            "rate_limiting": {
                "title": "Rate Limiting",
                "description": "Understanding and handling rate limits",
                "limits": {
                    "authenticated_users": "1000 requests per hour",
                    "unauthenticated": "100 requests per hour",
                    "webhook_endpoints": "10000 requests per hour"
                },
                "headers": {
                    "X-RateLimit-Limit": "Request limit per window",
                    "X-RateLimit-Remaining": "Remaining requests in current window", 
                    "X-RateLimit-Reset": "Time when the rate limit resets"
                },
                "best_practices": [
                    "Check rate limit headers in responses",
                    "Implement exponential backoff for 429 responses",
                    "Cache responses when possible to reduce API calls",
                    "Use webhooks instead of polling for real-time updates"
                ]
            },
            "webhooks": {
                "title": "Webhooks",
                "description": "Setting up webhooks for real-time notifications",
                "events": [
                    "message.received",
                    "lead.created", 
                    "lead.updated",
                    "invoice.paid",
                    "subscription.updated",
                    "kyb.alert.created"
                ],
                "setup": [
                    "1. Configure webhook URL in tenant settings",
                    "2. Verify webhook endpoint by responding to challenge",
                    "3. Process webhook events and respond with 200 status",
                    "4. Implement retry logic for failed webhook deliveries"
                ]
            },
            "sdks": {
                "title": "SDKs and Libraries",
                "description": "Available SDKs and community libraries",
                "official": [
                    {
                        "language": "JavaScript/Node.js",
                        "status": "Coming soon",
                        "repository": "https://github.com/ai-secretary/js-sdk"
                    },
                    {
                        "language": "Python",
                        "status": "Coming soon", 
                        "repository": "https://github.com/ai-secretary/python-sdk"
                    }
                ],
                "community": [
                    {
                        "language": "PHP",
                        "status": "Community maintained",
                        "repository": "https://github.com/community/ai-secretary-php"
                    }
                ]
            }
        }
        
        return success_response(
            message=_('Integration guide retrieved successfully'),
            data=guide
        )
        
    except Exception as e:
        return error_response(
            error_code='INTEGRATION_GUIDE_ERROR',
            message=_('Failed to load integration guide'),
            status_code=500,
            details=str(e)
        )