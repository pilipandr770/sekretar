# AI Secretary API Documentation

## Overview

AI Secretary API is a RESTful web service that provides intelligent assistant capabilities for managing communications, CRM, calendar, and knowledge base operations. The API is built with Flask and follows REST principles.

## Base URL

```
http://localhost:5000
```

## Authentication

Currently, the API operates in development mode without authentication. In production, JWT tokens will be required for protected endpoints.

## Content Type

All API endpoints accept and return JSON data unless otherwise specified.

```
Content-Type: application/json
```

## CORS

CORS is enabled for the following origins:
- `http://localhost:3000`
- `http://127.0.0.1:3000`

## API Endpoints

### 1. Welcome Endpoint

**GET /**

Returns basic API information and available endpoints.

**Response:**
```json
{
  "message": "Welcome to AI Secretary API",
  "version": "1.0.0",
  "environment": "development",
  "endpoints": {
    "health": "/api/v1/health",
    "version": "/api/v1/version",
    "auth": "/api/v1/auth",
    "docs": "/api/v1/docs"
  },
  "timestamp": "2025-08-11T09:00:00Z"
}
```

### 2. Health Check

**GET /api/v1/health**

Returns the health status of the system and its components.

**Response (Healthy):**
```json
{
  "status": "healthy",
  "timestamp": "2025-08-11T09:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "healthy",
      "response_time_ms": 15
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 5
    }
  }
}
```

**Response (Unhealthy):**
```json
{
  "status": "unhealthy",
  "timestamp": "2025-08-11T09:00:00Z",
  "version": "1.0.0",
  "checks": {
    "database": {
      "status": "unhealthy",
      "response_time_ms": null,
      "error": "Connection timeout"
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 3
    }
  }
}
```

**Status Codes:**
- `200 OK` - System is healthy or only Redis is unhealthy
- `503 Service Unavailable` - Database is unhealthy

### 3. Version Information

**GET /api/v1/version**

Returns version and build information.

**Response:**
```json
{
  "version": "1.0.0",
  "environment": "development",
  "python_version": "3.12.2",
  "flask_version": "3.1.1",
  "build_date": "2025-08-10T20:00:00Z"
}
```

### 4. System Status

**GET /api/v1/status**

Returns detailed system status with component information.

**Response:**
```json
{
  "success": true,
  "message": "System is operational",
  "data": {
    "service": "ai-secretary-api",
    "version": "1.0.0",
    "components": {
      "database": "healthy",
      "redis": "healthy",
      "celery": "healthy"
    },
    "language": "en"
  }
}
```

### 5. Available Languages

**GET /api/v1/languages**

Returns list of supported languages for internationalization.

**Response:**
```json
{
  "success": true,
  "message": "Available languages",
  "data": {
    "languages": {
      "en": "English",
      "de": "Deutsch",
      "uk": "Українська"
    },
    "current": "en"
  }
}
```

### 6. Set Language

**POST /api/v1/language**

Sets the user's language preference.

**Request Body:**
```json
{
  "language": "uk"
}
```

**Response (Success):**
```json
{
  "success": true,
  "message": "Language updated successfully",
  "data": {
    "language": "uk"
  }
}
```

**Response (Error):**
```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid language code. Available: en, de, uk"
  }
}
```

## Error Handling

The API uses standard HTTP status codes and returns consistent error responses.

### Error Response Format

```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable error message",
    "request_id": "req_123456789",
    "details": "Additional error details (optional)"
  }
}
```

### Common Error Codes

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `AUTHENTICATION_ERROR` | 401 | Authentication required |
| `AUTHORIZATION_ERROR` | 403 | Insufficient permissions |
| `NOT_FOUND_ERROR` | 404 | Resource not found |
| `METHOD_NOT_ALLOWED` | 405 | HTTP method not allowed |
| `CONFLICT_ERROR` | 409 | Resource already exists |
| `RATE_LIMIT_ERROR` | 429 | Rate limit exceeded |
| `INTERNAL_ERROR` | 500 | Internal server error |
| `HEALTH_CHECK_FAILED` | 503 | Health check service failed |

## Rate Limiting

Rate limiting is configured but not actively enforced in development mode. In production:
- Default limit: 100 requests per minute per IP
- Storage: Redis

## Internationalization

The API supports multiple languages:
- **English (en)** - Default
- **German (de)** - Deutsch
- **Ukrainian (uk)** - Українська

Language can be set via:
1. URL parameter: `?lang=uk`
2. Session storage
3. User profile (when authenticated)
4. Accept-Language header

## Web Interface

In addition to the API, a web interface is available:

- **Main Interface:** `http://localhost:5000/web`
- **Dashboard:** `http://localhost:5000/web/dashboard`
- **API Tester:** `http://localhost:5000/web/api-tester`

## Development

### Running the Server

```bash
# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows

# Run development server
python -m flask run --host=0.0.0.0 --port=5000
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run integration tests only
python -m pytest tests/test_api_integration.py -v

# Run with coverage
python -m pytest --cov=app tests/
```

### Environment Variables

Key environment variables (see `.env.example`):

```bash
FLASK_ENV=development
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://user:pass@localhost/db
REDIS_URL=redis://localhost:6379/0
API_VERSION=1.0.0
```

## Production Deployment

For production deployment:

1. Set `FLASK_ENV=production`
2. Configure PostgreSQL database
3. Configure Redis for caching
4. Set up proper SSL/TLS
5. Use a production WSGI server (Gunicorn, uWSGI)
6. Configure proper logging
7. Set up monitoring and health checks

## Support

For support and questions:
- GitHub Issues: [Project Repository]
- Email: support@ai-secretary.com
- Documentation: This file

## Changelog

### Version 1.0.0 (2025-08-11)
- Initial API implementation
- Basic endpoints (health, version, status)
- Web interface
- Internationalization support
- Integration tests
- CORS configuration