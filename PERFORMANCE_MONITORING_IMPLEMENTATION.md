# Performance Monitoring and Logging Implementation

## Overview

Successfully implemented a comprehensive performance monitoring and logging system for the AI Secretary application as part of task 9 from the app-critical-fixes specification.

## Components Implemented

### 1. Database Models (`app/models/performance.py`)

#### PerformanceMetric Model
- Tracks request performance metrics including response times, database query metrics, cache performance
- Stores user context, IP addresses, system resource usage
- Includes methods for logging requests, finding slow requests, and getting endpoint statistics
- Automatic cleanup of old metrics

#### SlowQuery Model  
- Logs slow database queries with normalized query text for analysis
- Tracks execution times, rows examined/returned, and context information
- Query normalization and hashing for efficient grouping and analysis
- Methods to find frequent slow queries

#### ServiceHealth Model
- Monitors health status of various services (database, cache, external APIs)
- Tracks response times, error messages, and service metadata
- Methods to update service status and get health summaries

#### PerformanceAlert Model
- Creates and manages performance-related alerts
- Supports different severity levels and alert types
- Tracks alert lifecycle (active, acknowledged, resolved)
- Automatic alert deduplication and occurrence counting

### 2. Performance Monitoring Core (`app/utils/performance_monitor.py`)

#### PerformanceMonitor Class
- Main monitoring class that integrates with Flask request lifecycle
- Automatic request performance tracking via before/after request hooks
- Database query monitoring using SQLAlchemy events
- System resource monitoring (CPU, memory, disk usage)
- Background monitoring thread for continuous health checks
- Automatic data cleanup based on retention policies

#### PerformanceCollector Class
- Static methods for collecting and aggregating performance data
- Endpoint performance summaries with statistics
- Slow query analysis and reporting
- System health status aggregation

### 3. Performance Alerting System (`app/utils/performance_alerts.py`)

#### AlertManager Class
- Manages alert notifications through multiple channels (email, Slack, webhooks)
- Configurable severity thresholds for different notification channels
- HTML email templates for alerts
- Slack integration with rich formatting
- Webhook support for custom integrations

#### PerformanceThresholdChecker Class
- Monitors performance metrics against configurable thresholds
- Checks error rates, response times, and system resources
- Automatic alert creation when thresholds are exceeded
- Configurable time windows for analysis

### 4. Performance Middleware (`app/utils/performance_middleware.py`)

#### PerformanceMiddleware Class
- Flask middleware integration for automatic performance monitoring
- Request/response time tracking
- Error handling integration
- Context management for performance data
- Decorators and context managers for monitoring specific code blocks

### 5. Celery Tasks (`app/tasks/performance_tasks.py`)

Background tasks for performance monitoring:
- `check_performance_thresholds`: Periodic threshold checking
- `send_performance_alerts`: Alert notification sending
- `cleanup_old_performance_data`: Data retention management
- `generate_performance_report`: Automated reporting
- `monitor_system_resources`: System resource monitoring
- `check_service_health`: External service health checks
- `analyze_performance_trends`: Trend analysis and anomaly detection

### 6. CLI Commands (`app/cli/performance.py`)

Comprehensive CLI interface for performance monitoring:
- `flask performance report`: Generate performance reports
- `flask performance slow-requests`: Show slow requests
- `flask performance alerts`: Manage performance alerts
- `flask performance cleanup`: Clean up old data
- `flask performance check-thresholds`: Manual threshold checking
- `flask performance send-alerts`: Send pending alerts
- `flask performance services`: Show service health status
- `flask performance analyze`: Detailed performance analysis

### 7. API Endpoints (`app/api/performance.py`)

REST API for performance monitoring:
- `/performance/metrics/summary`: Performance metrics overview
- `/performance/metrics/endpoints`: Endpoint-specific metrics
- `/performance/metrics/slow-requests`: Slow request analysis
- `/performance/metrics/slow-queries`: Slow query analysis
- `/performance/alerts`: Alert management
- `/performance/services/health`: Service health status
- `/performance/dashboard`: Performance dashboard data
- `/performance/config`: Configuration management

### 8. Database Migration

Created database tables for performance monitoring:
- `performance_metrics`: Request performance data
- `slow_queries`: Slow database query logs
- `service_health`: Service health status
- `performance_alerts`: Performance alerts
- Comprehensive indexing for efficient queries

## Configuration Options

Added extensive configuration options to `config.py`:

### Performance Monitoring Settings
- `MONITORING_ENABLED`: Enable/disable monitoring
- `PERFORMANCE_LOG_THRESHOLD_MS`: Threshold for logging slow operations
- `SLOW_QUERY_THRESHOLD_MS`: Database query slowness threshold
- `SLOW_REQUEST_THRESHOLD_MS`: Request slowness threshold
- `METRICS_RETENTION_DAYS`: Data retention period

### Alert Thresholds
- `CPU_ALERT_THRESHOLD`: CPU usage alert threshold
- `MEMORY_ALERT_THRESHOLD`: Memory usage alert threshold  
- `DISK_ALERT_THRESHOLD`: Disk usage alert threshold
- `ERROR_RATE_THRESHOLD`: Error rate alert threshold
- `RESPONSE_TIME_THRESHOLD`: Response time alert threshold

### Alerting Configuration
- Email alerting with SMTP configuration
- Slack webhook integration
- Custom webhook support
- Configurable severity levels and recipients

## Features

### Request Performance Tracking
- Automatic tracking of all HTTP requests
- Response time measurement
- Database query performance correlation
- Cache hit/miss tracking
- User and tenant context
- System resource usage correlation

### Database Query Monitoring
- Automatic slow query detection
- Query normalization and analysis
- Execution time tracking
- Query frequency analysis
- Context correlation with requests

### System Health Monitoring
- CPU, memory, and disk usage monitoring
- Service health checks (database, Redis, external APIs)
- Automatic service recovery attempts
- Health status dashboards

### Alerting and Notifications
- Multi-channel alert delivery
- Configurable severity levels
- Alert deduplication and aggregation
- Alert lifecycle management
- Rich formatting for different channels

### Performance Analytics
- Trend analysis over time
- Performance regression detection
- Endpoint performance comparison
- Resource usage correlation
- Automated reporting

### Data Management
- Configurable data retention
- Automatic cleanup of old data
- Efficient indexing for fast queries
- Data aggregation and summarization

## Integration

The performance monitoring system is fully integrated with the existing application:

1. **Middleware Integration**: Automatic request tracking via Flask middleware
2. **Database Integration**: SQLAlchemy event listeners for query monitoring
3. **Error Handling Integration**: Performance tracking for error scenarios
4. **CLI Integration**: Management commands for operations
5. **API Integration**: REST endpoints for external monitoring tools
6. **Background Tasks**: Celery tasks for automated monitoring

## Usage Examples

### CLI Usage
```bash
# Generate performance report
flask performance report --hours 24

# Show slow requests
flask performance slow-requests --threshold 2000

# Check service health
flask performance services

# Clean up old data
flask performance cleanup --days 30
```

### API Usage
```bash
# Get performance summary
curl /api/v1/performance/metrics/summary?hours=24

# Get slow requests
curl /api/v1/performance/metrics/slow-requests?threshold=2000

# Get service health
curl /api/v1/performance/services/health
```

### Programmatic Usage
```python
# Log custom performance metric
PerformanceMetric.log_request(
    endpoint='/custom-endpoint',
    method='POST',
    status_code=200,
    response_time_ms=150.5
)

# Create performance alert
PerformanceAlert.create_or_update_alert(
    alert_type='custom_alert',
    severity='medium',
    title='Custom Performance Issue',
    description='Custom performance issue detected'
)
```

## Benefits

1. **Proactive Monitoring**: Early detection of performance issues
2. **Root Cause Analysis**: Correlation between different performance metrics
3. **Automated Alerting**: Immediate notification of performance problems
4. **Historical Analysis**: Trend analysis and performance regression detection
5. **Operational Insights**: Understanding of system behavior and bottlenecks
6. **Scalability Planning**: Data-driven capacity planning decisions

## Next Steps

The performance monitoring system is now fully operational and provides:
- Real-time performance tracking
- Automated alerting for performance issues
- Historical performance analysis
- Service health monitoring
- Comprehensive reporting capabilities

The system will help identify and resolve the performance issues mentioned in the original requirements (slow response times, database bottlenecks, service failures) and provide ongoing monitoring to prevent future issues.