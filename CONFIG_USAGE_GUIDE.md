# Configuration Usage Guide

This guide explains how to use the enhanced configuration system with adaptive database configuration, SQLite support, and comprehensive error reporting.

## Overview

The updated configuration system provides:

- **Adaptive Database Configuration**: Automatically detects and configures PostgreSQL or SQLite
- **Service Detection**: Detects available services (Redis, external APIs) and adapts accordingly
- **SQLite-Specific Configuration**: Dedicated configuration class for SQLite mode
- **Configuration Validation**: Comprehensive validation with error reporting
- **Environment Variable Handling**: Enhanced environment variable management

## Configuration Classes

### Base Configuration Classes

- `Config`: Base configuration with all common settings
- `DevelopmentConfig`: Development-specific settings
- `TestingConfig`: Testing configuration with SQLite and disabled external services
- `ProductionConfig`: Production configuration with enhanced security
- `SQLiteConfig`: SQLite-specific configuration for local development

### Getting Configuration Classes

```python
from config import get_config_class

# Get configuration for specific environment
config_class = get_config_class('development')
config_class = get_config_class('sqlite')

# Auto-detect environment
config_class = get_config_class()
```

## Environment Variables

### Service Detection Configuration

```bash
# Enable/disable service detection
SERVICE_DETECTION_ENABLED=true
SERVICE_CONNECTION_TIMEOUT=5

# Database service detection
DATABASE_DETECTION_ENABLED=true
POSTGRESQL_FALLBACK_ENABLED=true
SQLITE_FALLBACK_ENABLED=true

# Cache service detection
CACHE_DETECTION_ENABLED=true
REDIS_FALLBACK_ENABLED=true
SIMPLE_CACHE_FALLBACK=true

# External service detection
EXTERNAL_SERVICE_DETECTION_ENABLED=true
EXTERNAL_SERVICE_TIMEOUT=10
```

### SQLite Configuration

```bash
# SQLite database configuration
SQLITE_DATABASE_URL=sqlite:///ai_secretary.db
SQLITE_TIMEOUT=20
SQLITE_CHECK_SAME_THREAD=false

# Force SQLite mode (overrides environment detection)
SQLITE_MODE=true
```

### Configuration Validation

```bash
# Enable configuration validation
CONFIG_VALIDATION_ENABLED=true
CONFIG_VALIDATION_STRICT=false
```

## Using SQLite Configuration

### Method 1: Environment Variable

Set `SQLITE_MODE=true` in your environment or `.env` file:

```bash
SQLITE_MODE=true
```

### Method 2: Direct Class Usage

```python
from config import SQLiteConfig

app.config.from_object(SQLiteConfig)
```

### Method 3: Environment-based Selection

```python
from config import get_config_class

# Will return SQLiteConfig if SQLITE_MODE=true
config_class = get_config_class()
app.config.from_object(config_class)
```

## Configuration Validation

### Validate Environment Variables

```python
from config import validate_environment_variables, create_error_report

# Validate environment variables
validation_results = validate_environment_variables()
error_report = create_error_report(validation_results)

print(error_report)
```

### Validate Configuration Class

```python
from config import Config

# Validate configuration
validation_results = Config.validate_configuration()

if not validation_results['valid']:
    print("Configuration errors:")
    for error in validation_results['errors']:
        print(f"  • {error}")
```

### Get Adaptive Configuration

```python
from config import Config

# Get adaptive database configuration
db_config = Config.get_adaptive_database_config()
print(f"Primary URL: {db_config['primary_url']}")
print(f"Fallback URL: {db_config['fallback_url']}")

# Get adaptive cache configuration
cache_config = Config.get_adaptive_cache_config()
print(f"Cache Type: {cache_config['primary_type']}")
print(f"Redis URL: {cache_config['redis_url']}")

# Get service detection configuration
service_config = Config.get_service_detection_config()
print(f"Detection Enabled: {service_config['enabled']}")
```

## Integration with Adaptive Config Manager

The enhanced configuration system works seamlessly with the existing `AdaptiveConfigManager`:

```python
from app.utils.adaptive_config import AdaptiveConfigManager
from config import get_config_class

# Create adaptive config manager
manager = AdaptiveConfigManager('development')

# Get adaptive configuration class
adaptive_config_class = manager.get_config_class()

# Or use the enhanced config system
enhanced_config_class = get_config_class('development')

# Both approaches work together
app.config.from_object(adaptive_config_class)
```

## SQLite Mode Features

When using SQLite configuration:

- **Database**: Uses SQLite instead of PostgreSQL
- **Schema**: Removes PostgreSQL schema configuration
- **Cache**: Uses simple cache instead of Redis
- **Celery**: Disabled (requires Redis)
- **Rate Limiting**: Disabled (requires Redis)
- **WebSockets**: Enabled (works without Redis)

## Validation Scripts

### Basic Validation

```bash
python validate_config.py
```

### Integration Testing

```bash
python test_config_integration.py
```

### Error Reporting Testing

```bash
python test_config_error_reporting.py
```

## Common Use Cases

### Local Development with SQLite

1. Set `SQLITE_MODE=true` in `.env`
2. Run the application - it will automatically use SQLite
3. All PostgreSQL-dependent features are gracefully disabled

### Production with PostgreSQL

1. Set proper `DATABASE_URL` for PostgreSQL
2. Ensure `SQLITE_MODE=false` or remove it
3. Configure Redis for caching and Celery

### Testing Environment

1. Use `TestingConfig` which automatically uses SQLite in-memory
2. All external services are disabled
3. Validation is relaxed for testing

### Configuration Debugging

1. Run `python validate_config.py` to check configuration
2. Check validation results for errors and warnings
3. Use adaptive configuration methods to inspect detected services

## Error Handling

The configuration system provides comprehensive error handling:

- **Missing Required Variables**: Clear error messages for missing environment variables
- **Configuration Conflicts**: Detection of conflicting settings (e.g., SQLite with schema)
- **Service Unavailability**: Graceful fallback when services are unavailable
- **Validation Errors**: Detailed validation results with specific error messages

## Best Practices

1. **Always validate configuration** in production environments
2. **Use environment variables** for all sensitive configuration
3. **Test with SQLite** for local development
4. **Enable service detection** for automatic fallback
5. **Monitor configuration warnings** for potential issues
6. **Use strict validation** in production environments

## Troubleshooting

### Common Issues

1. **"Required environment variable not set"**
   - Check your `.env` file
   - Ensure variables are properly loaded

2. **"Configuration conflicts detected"**
   - Check for incompatible settings (e.g., SQLite with schema)
   - Review configuration validation results

3. **"Service unavailable"**
   - Check if external services (PostgreSQL, Redis) are running
   - Enable fallback options in configuration

4. **"Database connection failed"**
   - Verify database URL format
   - Check database server availability
   - Ensure proper credentials

### Debug Commands

```bash
# Validate configuration
python validate_config.py

# Test configuration integration
python test_config_integration.py

# Test error reporting
python test_config_error_reporting.py

# Check environment variables
python -c "from config import validate_environment_variables; print(validate_environment_variables())"
```