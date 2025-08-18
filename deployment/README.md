# AI Secretary Production Deployment Guide

This directory contains all the necessary files and scripts for deploying the AI Secretary SaaS platform in a production environment.

## Overview

The production deployment uses Docker Compose to orchestrate multiple services:

- **Nginx**: Reverse proxy and load balancer
- **Flask App**: Main application (multiple instances)
- **Celery Workers**: Background task processing
- **Celery Beat**: Task scheduler
- **PostgreSQL**: Primary database
- **Redis**: Cache and message broker
- **Prometheus**: Metrics collection
- **Grafana**: Monitoring dashboards

## Prerequisites

- Docker and Docker Compose installed
- Domain name configured to point to your server
- SSL certificate (can be generated using included script)
- Required API keys and credentials

## Quick Start

1. **Generate secrets and environment configuration:**
   ```bash
   ./deployment/scripts/generate-secrets.sh
   ```

2. **Edit the generated `.env.prod` file with your actual values:**
   - OpenAI API key
   - Stripe credentials
   - Google OAuth credentials
   - Telegram bot token
   - Email settings
   - Domain configuration

3. **Set up SSL certificates:**
   ```bash
   ./deployment/scripts/ssl-setup.sh yourdomain.com admin@yourdomain.com
   ```

4. **Deploy the application:**
   ```bash
   ./deployment/scripts/deploy.sh
   ```

## Directory Structure

```
deployment/
├── README.md                 # This file
├── nginx/
│   ├── nginx.conf           # Nginx configuration
│   └── ssl/                 # SSL certificates directory
├── postgres/
│   ├── init/                # Database initialization scripts
│   └── backups/             # Database backups directory
├── redis/
│   └── redis.conf           # Redis configuration
├── prometheus/
│   └── prometheus.yml       # Prometheus configuration
├── grafana/
│   ├── provisioning/        # Grafana datasources and dashboards
│   └── dashboards/          # Custom dashboards
└── scripts/
    ├── generate-secrets.sh  # Generate secure secrets
    ├── deploy.sh           # Main deployment script
    ├── update.sh           # Zero-downtime update script
    ├── backup-database.sh  # Database backup script
    ├── restore-database.sh # Database restore script
    ├── migrate-database.sh # Database migration script
    └── ssl-setup.sh        # SSL certificate setup
```

## Configuration Files

### Environment Variables

The `.env.prod` file contains all environment variables needed for production:

- **Flask Configuration**: Secret keys, debug settings
- **Database**: PostgreSQL connection details
- **Redis**: Cache and message broker settings
- **External APIs**: OpenAI, Stripe, Google, Telegram
- **Email**: SMTP configuration
- **Monitoring**: Grafana credentials
- **Security**: CORS, CSRF settings

### Docker Compose Files

- `docker-compose.prod.yml`: Production services configuration
- `Dockerfile.prod`: Main application container
- `Dockerfile.worker`: Celery worker container
- `Dockerfile.scheduler`: Celery beat scheduler container

## Deployment Process

### Initial Deployment

1. **Prepare the server:**
   - Install Docker and Docker Compose
   - Configure firewall (ports 80, 443, 22)
   - Set up domain DNS

2. **Configure the application:**
   - Generate secrets: `./deployment/scripts/generate-secrets.sh`
   - Edit `.env.prod` with actual values
   - Set up SSL: `./deployment/scripts/ssl-setup.sh domain.com email@domain.com`

3. **Deploy:**
   ```bash
   ./deployment/scripts/deploy.sh
   ```

### Updates

For zero-downtime updates:

```bash
./deployment/scripts/update.sh
```

This script:
- Creates a database backup
- Pulls latest code (if using git)
- Builds new Docker images
- Runs database migrations
- Performs rolling update of services
- Verifies health checks

### Rollback

If an update fails:

```bash
./deployment/scripts/update.sh rollback
```

## Database Management

### Backups

Automatic backups are recommended via cron:

```bash
# Add to crontab for daily backups at 2 AM
0 2 * * * /path/to/deployment/scripts/backup-database.sh
```

Manual backup:
```bash
./deployment/scripts/backup-database.sh
```

### Restore

```bash
./deployment/scripts/restore-database.sh /backups/backup_file.sql.gz
```

### Migrations

```bash
./deployment/scripts/migrate-database.sh
```

## Monitoring

### Grafana Dashboards

Access Grafana at `http://your-domain:3000`:
- Username: admin
- Password: (from .env.prod GRAFANA_PASSWORD)

### Prometheus Metrics

Access Prometheus at `http://your-domain:9090`

### Application Logs

View logs for specific services:
```bash
./deployment/scripts/deploy.sh logs app
./deployment/scripts/deploy.sh logs worker
./deployment/scripts/deploy.sh logs nginx
```

## Security Considerations

### SSL/TLS

- Certificates are automatically renewed via cron
- Strong cipher suites configured in Nginx
- HSTS headers enabled

### Network Security

- Services communicate via internal Docker network
- Only necessary ports exposed (80, 443)
- Rate limiting configured in Nginx

### Application Security

- Secrets stored in environment variables
- Database credentials rotated regularly
- CSRF protection enabled
- CORS properly configured

## Scaling

### Horizontal Scaling

To scale application instances:

```bash
docker-compose -f docker-compose.prod.yml up -d --scale app=4 --scale worker=6
```

### Database Scaling

For high-traffic scenarios:
- Set up read replicas
- Configure connection pooling
- Implement database sharding if needed

### Load Balancing

Nginx is configured for load balancing across multiple app instances:
- Health checks enabled
- Failover configured
- Session persistence via Redis

## Troubleshooting

### Common Issues

1. **Service won't start:**
   ```bash
   docker-compose -f docker-compose.prod.yml logs service-name
   ```

2. **Database connection issues:**
   - Check PostgreSQL logs
   - Verify connection string in .env.prod
   - Ensure database is healthy

3. **SSL certificate issues:**
   - Check certificate expiry
   - Verify domain DNS
   - Run renewal script manually

### Health Checks

Check service health:
```bash
curl http://localhost/health
./deployment/scripts/deploy.sh status
```

### Performance Issues

Monitor resource usage:
```bash
docker stats
```

Check application metrics in Grafana dashboard.

## Maintenance

### Regular Tasks

1. **Weekly:**
   - Review application logs
   - Check disk space
   - Verify backups

2. **Monthly:**
   - Update Docker images
   - Review security patches
   - Rotate secrets if needed

3. **Quarterly:**
   - Performance review
   - Capacity planning
   - Security audit

### Updates

Keep the system updated:
- OS security patches
- Docker and Docker Compose updates
- Application dependencies
- SSL certificates (automated)

## Support

For deployment issues:
1. Check logs: `./deployment/scripts/deploy.sh logs`
2. Verify configuration: Review .env.prod
3. Check service status: `./deployment/scripts/deploy.sh status`
4. Review monitoring dashboards in Grafana

## Backup and Disaster Recovery

### Backup Strategy

- **Database**: Daily automated backups with 30-day retention
- **File uploads**: Regular sync to external storage
- **Configuration**: Version controlled deployment files

### Recovery Procedures

1. **Database recovery**: Use restore script with latest backup
2. **Full system recovery**: Redeploy from configuration files
3. **Partial recovery**: Restart specific services

### Testing Recovery

Regularly test backup and recovery procedures in staging environment.