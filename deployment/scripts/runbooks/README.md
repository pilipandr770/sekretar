# AI Secretary Runbooks

This directory contains operational runbooks for common issues and maintenance tasks in the AI Secretary platform.

## Available Runbooks

### System Issues
- [High CPU Usage](./high-cpu-usage.md) - Troubleshooting high CPU utilization
- [High Memory Usage](./high-memory-usage.md) - Resolving memory issues
- [Low Disk Space](./low-disk-space.md) - Managing disk space problems
- [High System Load](./high-system-load.md) - Addressing system load issues

### Application Issues
- [Application Down](./application-down.md) - Recovering from application outages
- [High Error Rate](./high-error-rate.md) - Investigating and fixing error spikes
- [High Response Time](./high-response-time.md) - Optimizing slow response times
- [Database Connections](./database-connections.md) - Managing database connection issues

### Database Issues
- [PostgreSQL Down](./postgresql-down.md) - Recovering from database outages
- [PostgreSQL Connections](./postgresql-connections.md) - Managing connection pool issues
- [PostgreSQL Slow Queries](./postgresql-slow-queries.md) - Optimizing database performance

### Cache Issues
- [Redis Down](./redis-down.md) - Recovering from Redis outages
- [Redis Memory](./redis-memory.md) - Managing Redis memory usage
- [Redis Connections](./redis-connections.md) - Handling Redis connection issues

### External API Issues
- [OpenAI API Errors](./openai-api-errors.md) - Handling OpenAI API failures
- [Stripe API Errors](./stripe-api-errors.md) - Resolving Stripe integration issues

### Business Metrics
- [Low Message Rate](./low-message-rate.md) - Investigating low message processing
- [Trial Expirations](./trial-expirations.md) - Managing trial conversion issues

## Runbook Structure

Each runbook follows a standard structure:

1. **Problem Description** - What the issue looks like
2. **Symptoms** - How to identify the problem
3. **Immediate Actions** - Quick steps to mitigate impact
4. **Investigation Steps** - How to diagnose the root cause
5. **Resolution Steps** - How to fix the issue
6. **Prevention** - How to prevent future occurrences
7. **Escalation** - When and how to escalate

## Using Runbooks

1. **Identify the Issue** - Use monitoring alerts or symptoms to identify the problem
2. **Find the Runbook** - Locate the appropriate runbook from the list above
3. **Follow the Steps** - Execute the runbook steps in order
4. **Document Actions** - Record what you did and the results
5. **Update if Needed** - Improve the runbook based on your experience

## Emergency Contacts

- **On-Call Engineer**: [Phone] - [Email]
- **Database Administrator**: [Phone] - [Email]
- **DevOps Lead**: [Phone] - [Email]
- **Product Owner**: [Phone] - [Email]

## Monitoring Links

- **Grafana Dashboard**: http://localhost:3000
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093
- **Application Health**: http://localhost:5000/api/v1/health

## Common Commands

### Health Checks
```bash
# Application health
curl http://localhost:5000/api/v1/health

# Service status
docker-compose -f docker-compose.prod.yml ps

# System resources
./deployment/scripts/performance-monitor.sh system
```

### Log Analysis
```bash
# Application logs
docker logs ai_secretary_app --tail 100

# Database logs
docker logs ai_secretary_postgres --tail 100

# System logs
journalctl -u docker -f
```

### Service Management
```bash
# Restart services
docker-compose -f docker-compose.prod.yml restart

# Scale services
docker-compose -f docker-compose.prod.yml scale worker=3

# Update services
./deployment/scripts/update.sh
```

## Contributing

When creating or updating runbooks:

1. Use the standard structure outlined above
2. Include specific commands and examples
3. Test the procedures before documenting
4. Keep language clear and concise
5. Include screenshots or diagrams when helpful
6. Update the main README when adding new runbooks

## Version History

- v1.0 - Initial runbook collection
- Last Updated: [Date]
- Maintained by: DevOps Team