# HealthValidator Usage Guide

The HealthValidator provides comprehensive health checking for external services with fallback modes and informative status messages.

## Features

- ✅ **Comprehensive Service Validation**: Checks database, cache, and external APIs
- 🔄 **Fallback Mode Support**: Provides alternative functionality when services are unavailable
- 💬 **Informative Messages**: Clear status messages with actionable recommendations
- 📊 **Detailed Reporting**: Comprehensive health reports with warnings and recommendations

## API Endpoints

### 1. Comprehensive Health Check
```
GET /api/health/comprehensive
Authorization: Bearer <token> (Admin required)
```

Returns detailed health status for all services with fallback information.

**Response Example:**
```json
{
  "success": true,
  "data": {
    "overall_status": "fallback",
    "services": {
      "database": {
        "status": "available",
        "response_time_ms": 45.2,
        "fallback_available": true
      },
      "openai": {
        "status": "fallback",
        "error_message": "OpenAI API key not configured",
        "fallback_available": true,
        "fallback_message": "AI features disabled - using basic text processing"
      }
    },
    "fallback_services": ["openai", "stripe"],
    "recommendations": [
      "Set OPENAI_API_KEY environment variable",
      "Configure Stripe for billing features"
    ]
  }
}
```

### 2. Validate Specific Service
```
POST /api/health/service/<service_name>/validate
Authorization: Bearer <token> (Admin required)
```

Validates a specific service (database, redis, openai, stripe, google_oauth, telegram, smtp).

### 3. Fallback Status
```
GET /api/health/fallback-status
Authorization: Bearer <token>
```

Returns information about services currently running in fallback mode.

## Service Status Types

- **🟢 Available**: Service is fully operational
- **🟡 Degraded**: Service has performance issues but is functional
- **🟠 Fallback**: Service is unavailable but fallback mode is active
- **🔴 Unavailable**: Service is down with no fallback available
- **⚪ Unknown**: Service status cannot be determined

## Supported Services

### Core Services
- **Database**: PostgreSQL/SQLite connectivity and performance
- **Redis**: Cache service with in-memory fallback
- **SMTP**: Email service (critical - no fallback)

### External APIs
- **OpenAI**: AI features with basic text processing fallback
- **Stripe**: Billing with manual processing fallback
- **Google OAuth**: Calendar integration with manual sync fallback
- **Telegram**: Notifications with email fallback

## Fallback Modes

When services are unavailable, the system automatically switches to fallback modes:

| Service | Fallback Available | Fallback Mode |
|---------|-------------------|---------------|
| OpenAI | ✅ Yes | Basic text processing |
| Stripe | ✅ Yes | Manual payment processing |
| Redis | ✅ Yes | In-memory cache |
| Google OAuth | ✅ Yes | Manual calendar sync |
| Telegram | ✅ Yes | Email notifications |
| Signal | ✅ Yes | Alternative messaging |
| Database | ✅ Yes | SQLite fallback |
| SMTP | ❌ No | Critical service |

## Usage Examples

### Python Code
```python
from app.services.health_validator import health_validator
import asyncio

# Validate all services
async def check_system_health():
    report = await health_validator.validate_all_services()
    summary = health_validator.generate_status_summary(report)
    
    print(f"Overall Status: {report.overall_status.value}")
    print(f"Services in Fallback: {len(report.fallback_services)}")
    
    for service, result in report.services.items():
        message = health_validator.get_service_status_message(service, result)
        print(message)

# Validate specific service
async def check_openai():
    result = await health_validator.validate_openai()
    print(f"OpenAI Status: {result.status.value}")
    if result.fallback_available:
        print(f"Fallback: {result.fallback_message}")

# Run validation
asyncio.run(check_system_health())
```

### CLI Testing
```bash
# Run simple tests
python simple_health_test.py

# Run integration tests
python integration_health_test.py
```

## Configuration

The HealthValidator automatically detects service availability based on environment variables:

```bash
# External Services
OPENAI_API_KEY=your-openai-key
STRIPE_SECRET_KEY=your-stripe-key
REDIS_URL=redis://localhost:6379
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
TELEGRAM_BOT_TOKEN=your-telegram-token

# Email Configuration
SMTP_SERVER=smtp.gmail.com
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_PORT=587
```

## Monitoring Integration

The HealthValidator integrates with the existing monitoring system:

- **Alerts**: Automatic alerts for service degradation
- **Metrics**: Response time and availability tracking  
- **Recovery**: Automatic recovery attempts for failed services
- **Notifications**: Status change notifications

## Best Practices

1. **Regular Monitoring**: Use the comprehensive endpoint for regular health checks
2. **Fallback Planning**: Ensure fallback modes meet your requirements
3. **Alert Configuration**: Set up alerts for critical service failures
4. **Performance Monitoring**: Monitor response times for early degradation detection
5. **Documentation**: Keep service dependencies documented

## Troubleshooting

### Common Issues

1. **Service Timeout**: Increase timeout values in configuration
2. **Authentication Errors**: Verify API keys and credentials
3. **Network Issues**: Check firewall and network connectivity
4. **Fallback Not Working**: Verify fallback configuration

### Debug Mode

Enable debug logging to see detailed validation information:

```python
import logging
logging.getLogger('app.services.health_validator').setLevel(logging.DEBUG)
```

## Implementation Status

✅ **Completed Features:**
- Comprehensive service validation
- Fallback mode detection and configuration
- Informative status messages with recommendations
- Integration with existing health API
- Async validation support
- Detailed reporting and summaries

This completes the implementation of task 6.3 "Система проверки здоровья сервисов" with all required functionality.