# High CPU Usage Runbook

## Problem Description
System CPU usage is consistently above 85% for more than 5 minutes, indicating potential performance issues or resource contention.

## Symptoms
- CPU usage > 85% for extended periods
- Slow application response times
- High system load averages
- Monitoring alerts for high CPU usage
- User reports of slow performance

## Immediate Actions

### 1. Assess Current State
```bash
# Check current CPU usage
top -bn1 | head -20

# Check system load
uptime

# Check running processes
ps aux --sort=-%cpu | head -20
```

### 2. Identify High CPU Processes
```bash
# Find top CPU consuming processes
top -bn1 | grep -E "(python|postgres|redis|nginx)" | head -10

# Check Docker container resource usage
docker stats --no-stream
```

### 3. Quick Mitigation
```bash
# If application processes are consuming high CPU
docker-compose -f docker-compose.prod.yml restart app

# Scale down non-essential workers temporarily
docker-compose -f docker-compose.prod.yml scale worker=1

# Check if any runaway processes need to be killed
# (Use with caution - identify the process first)
# kill -TERM <pid>
```

## Investigation Steps

### 1. Analyze Process Details
```bash
# Get detailed process information
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -20

# Check process tree
pstree -p

# Monitor CPU usage over time
iostat -c 1 10
```

### 2. Check Application Metrics
```bash
# Check application performance
curl http://localhost:5000/api/v1/monitoring/status

# Check Prometheus metrics
curl http://localhost:9090/api/v1/query?query=system_cpu_usage_percent

# Review application logs for errors
docker logs ai_secretary_app --tail 100 | grep -i error
```

### 3. Database Analysis
```bash
# Check for expensive database queries
docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -c "
SELECT pid, now() - pg_stat_activity.query_start AS duration, query 
FROM pg_stat_activity 
WHERE (now() - pg_stat_activity.query_start) > interval '1 minute'
ORDER BY duration DESC;"

# Check database CPU usage
docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -c "
SELECT schemaname,tablename,attname,n_distinct,correlation 
FROM pg_stats 
WHERE schemaname = 'ai_secretary' 
ORDER BY n_distinct DESC LIMIT 10;"
```

### 4. Check for Resource Leaks
```bash
# Monitor memory usage patterns
free -m -s 5

# Check for memory leaks in application
docker exec ai_secretary_app python -c "
import psutil
import os
process = psutil.Process(os.getpid())
print(f'Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB')
print(f'CPU: {process.cpu_percent()}%')
"

# Check file descriptor usage
lsof | wc -l
```

## Resolution Steps

### 1. Application-Level Fixes

#### Restart Application Services
```bash
# Graceful restart of application
docker-compose -f docker-compose.prod.yml restart app worker

# Check if restart resolved the issue
sleep 30
./deployment/scripts/performance-monitor.sh system
```

#### Optimize Application Configuration
```bash
# Check current worker configuration
docker-compose -f docker-compose.prod.yml config | grep -A 5 -B 5 worker

# Temporarily reduce worker count if needed
docker-compose -f docker-compose.prod.yml scale worker=2

# Check Celery worker status
docker exec ai_secretary_worker celery -A celery_app inspect active
```

### 2. Database Optimization

#### Kill Long-Running Queries
```bash
# Identify and kill problematic queries
docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -c "
SELECT pg_terminate_backend(pid) 
FROM pg_stat_activity 
WHERE state = 'active' 
AND now() - query_start > interval '5 minutes'
AND query NOT LIKE '%pg_stat_activity%';"
```

#### Optimize Database Performance
```bash
# Update table statistics
docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -c "ANALYZE;"

# Check for missing indexes
docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -c "
SELECT schemaname, tablename, attname, n_distinct, correlation
FROM pg_stats 
WHERE schemaname = 'ai_secretary' 
AND n_distinct > 100
ORDER BY n_distinct DESC;"
```

### 3. System-Level Fixes

#### Adjust Process Priorities
```bash
# Lower priority of non-critical processes
renice +10 $(pgrep -f "celery.*worker")

# Check current nice values
ps -eo pid,ni,cmd | grep -E "(python|postgres)"
```

#### Clean Up System Resources
```bash
# Clear system caches
sync && echo 3 > /proc/sys/vm/drop_caches

# Clean up temporary files
find /tmp -type f -atime +7 -delete

# Clean up Docker resources
docker system prune -f
```

### 4. Scaling Solutions

#### Horizontal Scaling
```bash
# Add more application instances
docker-compose -f docker-compose.prod.yml scale app=3

# Add more worker instances
docker-compose -f docker-compose.prod.yml scale worker=4

# Verify scaling
docker-compose -f docker-compose.prod.yml ps
```

#### Load Balancing Check
```bash
# Check nginx configuration
docker exec ai_secretary_nginx nginx -t

# Reload nginx configuration
docker exec ai_secretary_nginx nginx -s reload

# Check load balancing status
curl -I http://localhost/api/v1/health
```

## Prevention

### 1. Monitoring Improvements
```bash
# Set up more granular CPU monitoring
# Add to prometheus.yml:
# - job_name: 'node-detailed'
#   static_configs:
#     - targets: ['node-exporter:9100']
#   scrape_interval: 15s
```

### 2. Application Optimization
- Implement connection pooling
- Add caching layers
- Optimize database queries
- Use async processing for heavy tasks
- Implement rate limiting

### 3. Infrastructure Improvements
- Consider vertical scaling (more CPU cores)
- Implement auto-scaling policies
- Set up proper resource limits
- Use CPU affinity for critical processes

### 4. Regular Maintenance
```bash
# Schedule regular performance checks
# Add to crontab:
# 0 */6 * * * /path/to/deployment/scripts/performance-monitor.sh report >> /var/log/performance-check.log

# Regular database maintenance
# 0 2 * * 0 docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -c "VACUUM ANALYZE;"
```

## Escalation

### When to Escalate
- CPU usage remains > 90% after initial mitigation
- Application becomes completely unresponsive
- Database performance severely degraded
- Multiple services affected simultaneously
- Root cause cannot be identified within 30 minutes

### Escalation Steps
1. **Immediate**: Contact on-call engineer
2. **15 minutes**: Notify DevOps lead
3. **30 minutes**: Engage database administrator
4. **1 hour**: Notify product owner and consider maintenance window

### Emergency Contacts
- **On-Call Engineer**: [Phone] - [Email]
- **DevOps Lead**: [Phone] - [Email]
- **Database Administrator**: [Phone] - [Email]

## Post-Incident Actions

### 1. Document the Incident
- Record timeline of events
- Document root cause analysis
- Note what worked and what didn't
- Update monitoring thresholds if needed

### 2. Implement Improvements
- Apply permanent fixes identified during resolution
- Update monitoring and alerting
- Improve documentation based on lessons learned
- Schedule follow-up reviews

### 3. Update Runbook
- Add new troubleshooting steps discovered
- Update commands that didn't work as expected
- Include new monitoring queries or tools used
- Share learnings with the team

## Related Runbooks
- [High Memory Usage](./high-memory-usage.md)
- [High System Load](./high-system-load.md)
- [Application Down](./application-down.md)
- [PostgreSQL Slow Queries](./postgresql-slow-queries.md)

---
**Last Updated**: [Date]  
**Version**: 1.0  
**Maintained by**: DevOps Team