# Translation System Production Deployment Guide

This guide covers the deployment of the AI Secretary translation system with production optimizations, monitoring, and alerting.

## Overview

The translation system includes:
- Automated translation compilation in build process
- Multi-level caching (memory, Redis, Flask-Cache)
- Performance monitoring with Prometheus metrics
- Health checking and alerting
- Backup and recovery procedures
- Grafana dashboards for monitoring

## Prerequisites

- Docker and Docker Compose
- Access to production environment
- Environment variables configured
- SSL certificates (for HTTPS)
- SMTP server (for alerts)

## Environment Variables

Create a `.env.prod` file with the following variables:

```bash
# Database
DATABASE_URL=postgresql://user:password@db:5432/ai_secretary
POSTGRES_USER=ai_secretary_user
POSTGRES_PASSWORD=secure_password
POSTGRES_DB=ai_secretary

# Redis
REDIS_URL=redis://:redis_password@redis:6379/0
REDIS_PASSWORD=secure_redis_password

# Application
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here
FLASK_ENV=production

# Translation System
TRANSLATION_CACHE_ENABLED=true
TRANSLATION_MONITORING_ENABLED=true
I18N_PERFORMANCE_MONITORING=true
TRANSLATION_ALERT_RECIPIENTS=admin@yourcompany.com,devops@yourcompany.com
BABEL_DEFAULT_LOCALE=en
BABEL_DEFAULT_TIMEZONE=UTC

# Backup Settings
TRANSLATION_BACKUP_SCHEDULE=0 2 * * *
TRANSLATION_BACKUP_RETENTION=30

# Monitoring
GRAFANA_USER=admin
GRAFANA_PASSWORD=secure_grafana_password

# External Services
OPENAI_API_KEY=your-openai-key
STRIPE_SECRET_KEY=your-stripe-key
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Email (for alerts)
MAIL_SERVER=smtp.yourcompany.com
MAIL_PORT=587
MAIL_USERNAME=alerts@yourcompany.com
MAIL_PASSWORD=email_password
```

## Deployment Steps

### 1. Pre-deployment Preparation

```bash
# Clone the repository
git clone <repository-url>
cd ai-secretary

# Ensure translation files are ready
./scripts/i18n-workflow.ps1 full

# Build production image with translations
./scripts/build-production.ps1 -Tag v1.0.0
```

### 2. Deploy to Production

```bash
# Deploy with optimized configuration
docker-compose -f deployment/docker-compose.prod-optimized.yml up -d

# Verify deployment
docker-compose -f deployment/docker-compose.prod-optimized.yml ps
```

### 3. Verify Translation System

```bash
# Run health check
./deployment/scripts/translation-health-check.ps1 -Environment production -Detailed

# Check translation endpoints
curl https://your-domain.com/api/v1/languages
curl "https://your-domain.com/api/v1/translate?key=Welcome&lang=de"
```

### 4. Configure Monitoring

Access Grafana at `http://your-domain:3000`:
1. Login with configured credentials
2. Import translation dashboard from `deployment/monitoring/grafana/dashboards/translation-dashboard.json`
3. Configure alert channels (email, Slack, etc.)

Access Prometheus at `http://your-domain:9090`:
1. Verify translation metrics are being collected
2. Check alert rules are loaded

## Monitoring and Alerting

### Available Metrics

- `translation_requests_total` - Total translation requests
- `translation_response_time_seconds` - Response time histogram
- `translation_cache_hits_total` - Cache hits
- `translation_cache_misses_total` - Cache misses
- `translation_errors_total` - Translation errors
- `translation_file_size_bytes` - Translation file sizes
- `translation_coverage_percentage` - Translation coverage

### Alert Rules

Critical alerts:
- High response time (>2s)
- Low cache hit rate (<20%)
- High error rate (>15%)
- Low translation coverage (<60%)
- Missing translation files

Warning alerts:
- Moderate response time (>0.5s)
- Moderate cache hit rate (<50%)
- Moderate error rate (>5%)
- Moderate translation coverage (<80%)

### Health Check Endpoints

- `/api/v1/health` - General application health
- `/admin/translation/health` - Translation system health
- `/admin/translation/alerts` - Active translation alerts
- `/admin/translation/metrics` - Prometheus metrics
- `/admin/translation/dashboard` - Monitoring dashboard data

## Backup and Recovery

### Automated Backups

Translation files are automatically backed up daily at 2 AM:
- Location: `deployment/backups/translations/`
- Retention: 30 days (configurable)
- Format: Compressed tar.gz files

### Manual Backup

```bash
# Create manual backup
./deployment/scripts/deploy-translations.ps1 -Environment production -Version manual-backup
```

### Recovery Procedure

```bash
# List available backups
ls deployment/backups/translations/

# Restore from backup
./deployment/scripts/deploy-translations.ps1 -Environment production -Rollback -RollbackVersion backup-name
```

## Performance Optimization

### Caching Strategy

1. **Memory Cache** - Fastest, limited size
2. **Redis Cache** - Shared across instances
3. **Flask Cache** - Application-level caching

### Cache Warming

Cache is automatically warmed on application startup with common translations.

### Performance Monitoring

Monitor these key metrics:
- Cache hit rate (target: >80%)
- Response time (target: <500ms)
- Error rate (target: <1%)
- Memory usage
- Disk usage

## Troubleshooting

### Common Issues

1. **Translation files missing**
   ```bash
   # Rebuild with translations
   ./scripts/build-production.ps1 -Tag latest
   docker-compose -f deployment/docker-compose.prod-optimized.yml up -d --build app
   ```

2. **High response times**
   - Check cache hit rate
   - Verify Redis connectivity
   - Monitor system resources

3. **Cache issues**
   ```bash
   # Clear Redis cache
   docker-compose -f deployment/docker-compose.prod-optimized.yml exec redis redis-cli -a $REDIS_PASSWORD FLUSHDB
   ```

4. **Missing translations**
   ```bash
   # Update translations
   ./scripts/i18n-workflow.ps1 full
   ./deployment/scripts/deploy-translations.ps1 -Environment production
   ```

### Log Locations

- Application logs: `./logs/`
- Translation health logs: `./logs/translation-health.log`
- Docker logs: `docker-compose logs -f service-name`

### Debug Commands

```bash
# Check translation file status
./scripts/translation-status.ps1

# Test translation system
./deployment/scripts/translation-health-check.ps1 -Environment production -Detailed

# View cache statistics
curl https://your-domain.com/admin/translation/dashboard

# Check Prometheus metrics
curl https://your-domain.com/admin/translation/metrics
```

## Scaling Considerations

### Horizontal Scaling

- Multiple app instances share Redis cache
- Load balancer distributes requests
- Database connection pooling

### Vertical Scaling

- Increase memory for better caching
- More CPU cores for faster processing
- SSD storage for better I/O

### Cache Scaling

- Redis cluster for high availability
- Separate cache instances for different data types
- Cache partitioning by language

## Security Considerations

### Access Control

- Translation admin endpoints require authentication
- Monitoring dashboards behind authentication
- API rate limiting enabled

### Data Protection

- Translation files backed up securely
- Sensitive configuration in environment variables
- SSL/TLS for all communications

### Monitoring Security

- Alert on unusual translation patterns
- Monitor for potential attacks
- Log all administrative actions

## Maintenance Procedures

### Regular Tasks

1. **Weekly**
   - Review translation coverage reports
   - Check cache performance metrics
   - Verify backup integrity

2. **Monthly**
   - Update translation files
   - Review and update alert thresholds
   - Performance optimization review

3. **Quarterly**
   - Security audit
   - Disaster recovery testing
   - Capacity planning review

### Update Procedures

1. **Translation Updates**
   ```bash
   # Extract new messages
   ./scripts/i18n-workflow.ps1 extract
   
   # Update translations (manual editing required)
   # Edit .po files in app/translations/*/LC_MESSAGES/
   
   # Deploy updates
   ./deployment/scripts/deploy-translations.ps1 -Environment production
   ```

2. **System Updates**
   ```bash
   # Build new version
   ./scripts/build-production.ps1 -Tag v1.1.0
   
   # Deploy with zero downtime
   docker-compose -f deployment/docker-compose.prod-optimized.yml up -d --build
   ```

## Support and Contacts

- **Development Team**: dev@yourcompany.com
- **DevOps Team**: devops@yourcompany.com
- **Emergency Contact**: +1-xxx-xxx-xxxx

## Additional Resources

- [Translation System Architecture](../docs/TRANSLATION_ARCHITECTURE.md)
- [API Documentation](../docs/API_DOCUMENTATION.md)
- [Monitoring Runbooks](../docs/MONITORING_RUNBOOKS.md)
- [Security Guidelines](../docs/SECURITY_GUIDELINES.md)