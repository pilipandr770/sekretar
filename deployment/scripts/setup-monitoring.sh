#!/bin/bash

# Comprehensive monitoring setup script for AI Secretary
# This script sets up Prometheus, Grafana, Alertmanager, and related monitoring infrastructure

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
MONITORING_DIR="$PROJECT_ROOT/deployment"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_step "Checking prerequisites..."
    
    # Check if Docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install Docker first."
        exit 1
    fi
    
    # Check if Docker Compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed. Please install Docker Compose first."
        exit 1
    fi
    
    # Check if we're in the right directory
    if [ ! -f "$PROJECT_ROOT/docker-compose.prod.yml" ]; then
        log_error "docker-compose.prod.yml not found. Please run this script from the project root."
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Create monitoring directories
create_directories() {
    log_step "Creating monitoring directories..."
    
    mkdir -p "$MONITORING_DIR/prometheus/data"
    mkdir -p "$MONITORING_DIR/grafana/data"
    mkdir -p "$MONITORING_DIR/grafana/logs"
    mkdir -p "$MONITORING_DIR/grafana/provisioning/datasources"
    mkdir -p "$MONITORING_DIR/grafana/provisioning/dashboards"
    mkdir -p "$MONITORING_DIR/grafana/provisioning/notifiers"
    mkdir -p "$MONITORING_DIR/alertmanager/data"
    mkdir -p "$MONITORING_DIR/node-exporter"
    
    # Set proper permissions
    sudo chown -R 472:472 "$MONITORING_DIR/grafana" 2>/dev/null || true
    sudo chown -R 65534:65534 "$MONITORING_DIR/prometheus" 2>/dev/null || true
    sudo chown -R 65534:65534 "$MONITORING_DIR/alertmanager" 2>/dev/null || true
    
    log_info "Monitoring directories created"
}

# Setup Grafana datasources
setup_grafana_datasources() {
    log_step "Setting up Grafana datasources..."
    
    cat > "$MONITORING_DIR/grafana/provisioning/datasources/prometheus.yml" << 'EOF'
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: true
    jsonData:
      timeInterval: "30s"
      queryTimeout: "60s"
      httpMethod: "POST"
    
  - name: Alertmanager
    type: alertmanager
    access: proxy
    url: http://alertmanager:9093
    editable: true
    jsonData:
      implementation: "prometheus"
EOF

    log_info "Grafana datasources configured"
}

# Setup Grafana dashboard provisioning
setup_grafana_dashboards() {
    log_step "Setting up Grafana dashboard provisioning..."
    
    cat > "$MONITORING_DIR/grafana/provisioning/dashboards/dashboards.yml" << 'EOF'
apiVersion: 1

providers:
  - name: 'AI Secretary Dashboards'
    orgId: 1
    folder: 'AI Secretary'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 10
    allowUiUpdates: true
    options:
      path: /etc/grafana/provisioning/dashboards
EOF

    # Copy dashboard files
    if [ -f "$MONITORING_DIR/grafana/dashboards/ai-secretary-overview.json" ]; then
        cp "$MONITORING_DIR/grafana/dashboards/"*.json "$MONITORING_DIR/grafana/provisioning/dashboards/"
    fi
    
    log_info "Grafana dashboards configured"
}

# Setup Alertmanager configuration
setup_alertmanager() {
    log_step "Setting up Alertmanager..."
    
    if [ ! -f "$MONITORING_DIR/alertmanager/alertmanager.yml" ]; then
        cat > "$MONITORING_DIR/alertmanager/alertmanager.yml" << 'EOF'
global:
  smtp_smarthost: '${SMTP_HOST}:${SMTP_PORT}'
  smtp_from: '${ALERT_FROM_EMAIL}'
  smtp_auth_username: '${SMTP_USERNAME}'
  smtp_auth_password: '${SMTP_PASSWORD}'
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
  - match:
      severity: critical
    receiver: 'critical-alerts'
    group_wait: 5s
    repeat_interval: 5m
  - match:
      severity: warning
    receiver: 'warning-alerts'
    repeat_interval: 30m

receivers:
- name: 'default'
  webhook_configs:
  - url: 'http://app:5000/api/v1/monitoring/webhooks/alerts'
    send_resolved: true
    http_config:
      basic_auth:
        username: '${WEBHOOK_USERNAME}'
        password: '${WEBHOOK_PASSWORD}'

- name: 'critical-alerts'
  email_configs:
  - to: '${CRITICAL_ALERT_EMAIL}'
    subject: '[CRITICAL] AI Secretary Alert: {{ .GroupLabels.alertname }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Severity: {{ .Labels.severity }}
      Instance: {{ .Labels.instance }}
      Started: {{ .StartsAt }}
      {{ if .EndsAt }}Ended: {{ .EndsAt }}{{ end }}
      
      Runbook: {{ .Annotations.runbook_url }}
      {{ end }}
  slack_configs:
  - api_url: '${SLACK_WEBHOOK_URL}'
    channel: '#alerts'
    title: '[CRITICAL] AI Secretary Alert'
    text: '{{ range .Alerts }}{{ .Annotations.summary }}: {{ .Annotations.description }}{{ end }}'
    send_resolved: true

- name: 'warning-alerts'
  email_configs:
  - to: '${WARNING_ALERT_EMAIL}'
    subject: '[WARNING] AI Secretary Alert: {{ .GroupLabels.alertname }}'
    body: |
      {{ range .Alerts }}
      Alert: {{ .Annotations.summary }}
      Description: {{ .Annotations.description }}
      Severity: {{ .Labels.severity }}
      Instance: {{ .Labels.instance }}
      Started: {{ .StartsAt }}
      {{ if .EndsAt }}Ended: {{ .EndsAt }}{{ end }}
      {{ end }}

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
EOF
    fi
    
    log_info "Alertmanager configured"
}

# Setup Node Exporter configuration
setup_node_exporter() {
    log_step "Setting up Node Exporter..."
    
    cat > "$MONITORING_DIR/node-exporter/node-exporter.yml" << 'EOF'
# Node Exporter configuration
# Collects system metrics like CPU, memory, disk, network
collectors:
  enabled:
    - cpu
    - diskstats
    - filesystem
    - loadavg
    - meminfo
    - netdev
    - netstat
    - stat
    - time
    - uname
    - vmstat
EOF

    log_info "Node Exporter configured"
}

# Update Docker Compose with monitoring services
update_docker_compose() {
    log_step "Updating Docker Compose configuration..."
    
    # Check if monitoring services are already in docker-compose.prod.yml
    if grep -q "prometheus:" "$PROJECT_ROOT/docker-compose.prod.yml"; then
        log_warn "Monitoring services already exist in docker-compose.prod.yml"
        return
    fi
    
    # Backup original file
    cp "$PROJECT_ROOT/docker-compose.prod.yml" "$PROJECT_ROOT/docker-compose.prod.yml.backup"
    
    # Add monitoring services
    cat >> "$PROJECT_ROOT/docker-compose.prod.yml" << 'EOF'

  # Monitoring Services
  prometheus:
    image: prom/prometheus:latest
    container_name: ai_secretary_prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./deployment/prometheus/prometheus.yml:/etc/prometheus/prometheus.yml:ro
      - ./deployment/prometheus/rules:/etc/prometheus/rules:ro
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.path=/prometheus'
      - '--web.console.libraries=/etc/prometheus/console_libraries'
      - '--web.console.templates=/etc/prometheus/consoles'
      - '--storage.tsdb.retention.time=30d'
      - '--web.enable-lifecycle'
      - '--web.enable-admin-api'
    restart: unless-stopped
    networks:
      - ai_secretary_network

  grafana:
    image: grafana/grafana:latest
    container_name: ai_secretary_grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana_data:/var/lib/grafana
      - ./deployment/grafana/provisioning:/etc/grafana/provisioning:ro
      - ./deployment/grafana/dashboards:/etc/grafana/provisioning/dashboards:ro
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD:-admin}
      - GF_USERS_ALLOW_SIGN_UP=false
      - GF_INSTALL_PLUGINS=grafana-clock-panel,grafana-simple-json-datasource
    restart: unless-stopped
    networks:
      - ai_secretary_network

  alertmanager:
    image: prom/alertmanager:latest
    container_name: ai_secretary_alertmanager
    ports:
      - "9093:9093"
    volumes:
      - ./deployment/alertmanager/alertmanager.yml:/etc/alertmanager/alertmanager.yml:ro
      - alertmanager_data:/alertmanager
    command:
      - '--config.file=/etc/alertmanager/alertmanager.yml'
      - '--storage.path=/alertmanager'
      - '--web.external-url=http://localhost:9093'
      - '--cluster.advertise-address=0.0.0.0:9093'
    restart: unless-stopped
    networks:
      - ai_secretary_network

  node-exporter:
    image: prom/node-exporter:latest
    container_name: ai_secretary_node_exporter
    ports:
      - "9100:9100"
    volumes:
      - /proc:/host/proc:ro
      - /sys:/host/sys:ro
      - /:/rootfs:ro
    command:
      - '--path.procfs=/host/proc'
      - '--path.rootfs=/rootfs'
      - '--path.sysfs=/host/sys'
      - '--collector.filesystem.mount-points-exclude=^/(sys|proc|dev|host|etc)($$|/)'
    restart: unless-stopped
    networks:
      - ai_secretary_network

  postgres-exporter:
    image: prometheuscommunity/postgres-exporter:latest
    container_name: ai_secretary_postgres_exporter
    ports:
      - "9187:9187"
    environment:
      - DATA_SOURCE_NAME=postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}?sslmode=disable
    depends_on:
      - postgres
    restart: unless-stopped
    networks:
      - ai_secretary_network

  redis-exporter:
    image: oliver006/redis_exporter:latest
    container_name: ai_secretary_redis_exporter
    ports:
      - "9121:9121"
    environment:
      - REDIS_ADDR=redis://redis:6379
    depends_on:
      - redis
    restart: unless-stopped
    networks:
      - ai_secretary_network

  nginx-exporter:
    image: nginx/nginx-prometheus-exporter:latest
    container_name: ai_secretary_nginx_exporter
    ports:
      - "9113:9113"
    command:
      - '-nginx.scrape-uri=http://nginx:8080/nginx_status'
    depends_on:
      - nginx
    restart: unless-stopped
    networks:
      - ai_secretary_network
EOF

    # Add volumes section if it doesn't exist
    if ! grep -q "volumes:" "$PROJECT_ROOT/docker-compose.prod.yml"; then
        echo "" >> "$PROJECT_ROOT/docker-compose.prod.yml"
        echo "volumes:" >> "$PROJECT_ROOT/docker-compose.prod.yml"
    fi
    
    # Add monitoring volumes
    cat >> "$PROJECT_ROOT/docker-compose.prod.yml" << 'EOF'
  prometheus_data:
    driver: local
  grafana_data:
    driver: local
  alertmanager_data:
    driver: local
EOF

    log_info "Docker Compose configuration updated"
}

# Create monitoring environment variables
create_monitoring_env() {
    log_step "Creating monitoring environment variables..."
    
    if [ ! -f "$PROJECT_ROOT/.env.monitoring" ]; then
        cat > "$PROJECT_ROOT/.env.monitoring" << 'EOF'
# Monitoring Configuration
GRAFANA_ADMIN_PASSWORD=admin123
PROMETHEUS_RETENTION_DAYS=30

# Alerting Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=alerts@yourdomain.com
CRITICAL_ALERT_EMAIL=critical@yourdomain.com
WARNING_ALERT_EMAIL=warnings@yourdomain.com

# Slack Integration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK

# Webhook Authentication
WEBHOOK_USERNAME=monitoring
WEBHOOK_PASSWORD=secure-webhook-password

# PagerDuty Integration (optional)
PAGERDUTY_INTEGRATION_KEY=your-pagerduty-integration-key
EOF
        
        log_info "Monitoring environment file created at .env.monitoring"
        log_warn "Please update .env.monitoring with your actual configuration values"
    else
        log_info "Monitoring environment file already exists"
    fi
}

# Create health check script
create_health_check_script() {
    log_step "Creating health check script..."
    
    cat > "$PROJECT_ROOT/deployment/scripts/health-check.sh" << 'EOF'
#!/bin/bash

# Health check script for AI Secretary monitoring

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
APP_URL="http://localhost:5000"
PROMETHEUS_URL="http://localhost:9090"
GRAFANA_URL="http://localhost:3000"
ALERTMANAGER_URL="http://localhost:9093"

echo "AI Secretary Health Check"
echo "========================"

# Check application health
echo -n "Application Health: "
if curl -f -s "$APP_URL/api/v1/health" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check application readiness
echo -n "Application Readiness: "
if curl -f -s "$APP_URL/api/v1/health/ready" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Prometheus
echo -n "Prometheus: "
if curl -f -s "$PROMETHEUS_URL/-/healthy" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Grafana
echo -n "Grafana: "
if curl -f -s "$GRAFANA_URL/api/health" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Alertmanager
echo -n "Alertmanager: "
if curl -f -s "$ALERTMANAGER_URL/-/healthy" > /dev/null; then
    echo -e "${GREEN}OK${NC}"
else
    echo -e "${RED}FAILED${NC}"
fi

# Check Docker services
echo ""
echo "Docker Services Status:"
docker-compose -f docker-compose.prod.yml ps
EOF

    chmod +x "$PROJECT_ROOT/deployment/scripts/health-check.sh"
    
    log_info "Health check script created"
}

# Create smoke test script
create_smoke_test_script() {
    log_step "Creating smoke test script..."
    
    cat > "$PROJECT_ROOT/deployment/scripts/smoke-test.sh" << 'EOF'
#!/bin/bash

# Smoke test script for AI Secretary

set -e

APP_URL="http://localhost:5000"

echo "Running AI Secretary Smoke Tests"
echo "================================"

# Test health endpoint
echo -n "Testing health endpoint... "
if curl -f -s "$APP_URL/api/v1/health" | grep -q "healthy"; then
    echo "PASS"
else
    echo "FAIL"
    exit 1
fi

# Test metrics endpoint
echo -n "Testing metrics endpoint... "
if curl -f -s "$APP_URL/api/v1/metrics" | grep -q "flask_requests_total"; then
    echo "PASS"
else
    echo "FAIL"
    exit 1
fi

# Test monitoring status
echo -n "Testing monitoring status... "
if curl -f -s "$APP_URL/api/v1/monitoring/status" | grep -q "overall_status"; then
    echo "PASS"
else
    echo "FAIL"
    exit 1
fi

echo ""
echo "All smoke tests passed!"
EOF

    chmod +x "$PROJECT_ROOT/deployment/scripts/smoke-test.sh"
    
    log_info "Smoke test script created"
}

# Start monitoring services
start_monitoring() {
    log_step "Starting monitoring services..."
    
    cd "$PROJECT_ROOT"
    
    # Load environment variables
    if [ -f ".env.monitoring" ]; then
        set -a
        source .env.monitoring
        set +a
    fi
    
    # Start services
    docker-compose -f docker-compose.prod.yml up -d prometheus grafana alertmanager node-exporter postgres-exporter redis-exporter
    
    # Wait for services to be ready
    echo "Waiting for services to start..."
    sleep 30
    
    # Check if services are running
    if docker-compose -f docker-compose.prod.yml ps | grep -q "Up"; then
        log_info "Monitoring services started successfully"
    else
        log_error "Some monitoring services failed to start"
        docker-compose -f docker-compose.prod.yml ps
        exit 1
    fi
}

# Display access information
display_access_info() {
    log_step "Monitoring setup completed!"
    
    echo ""
    echo "Access Information:"
    echo "=================="
    echo "Grafana Dashboard:    http://localhost:3000 (admin/admin123)"
    echo "Prometheus:           http://localhost:9090"
    echo "Alertmanager:         http://localhost:9093"
    echo "Application Health:   http://localhost:5000/api/v1/health"
    echo "Application Metrics:  http://localhost:5000/api/v1/metrics"
    echo ""
    echo "Next Steps:"
    echo "==========="
    echo "1. Update .env.monitoring with your email and Slack settings"
    echo "2. Import additional Grafana dashboards if needed"
    echo "3. Configure notification channels in Grafana"
    echo "4. Test alerting by triggering a test alert"
    echo "5. Review and customize alert rules in deployment/prometheus/rules/"
    echo ""
    echo "Useful Commands:"
    echo "==============="
    echo "Health Check:         ./deployment/scripts/health-check.sh"
    echo "Smoke Test:           ./deployment/scripts/smoke-test.sh"
    echo "View Logs:            docker-compose -f docker-compose.prod.yml logs -f [service]"
    echo "Restart Services:     docker-compose -f docker-compose.prod.yml restart"
    echo ""
}

# Main execution
main() {
    echo "AI Secretary Monitoring Setup"
    echo "============================="
    echo ""
    
    check_prerequisites
    create_directories
    setup_grafana_datasources
    setup_grafana_dashboards
    setup_alertmanager
    setup_node_exporter
    update_docker_compose
    create_monitoring_env
    create_health_check_script
    create_smoke_test_script
    
    # Ask if user wants to start services now
    read -p "Do you want to start monitoring services now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_monitoring
    else
        log_info "Monitoring services not started. Run 'docker-compose -f docker-compose.prod.yml up -d' to start them."
    fi
    
    display_access_info
}

# Handle script arguments
case "${1:-setup}" in
    "setup")
        main
        ;;
    "start")
        start_monitoring
        ;;
    "health")
        "$PROJECT_ROOT/deployment/scripts/health-check.sh"
        ;;
    "test")
        "$PROJECT_ROOT/deployment/scripts/smoke-test.sh"
        ;;
    *)
        echo "Usage: $0 {setup|start|health|test}"
        echo "  setup - Set up monitoring infrastructure (default)"
        echo "  start - Start monitoring services"
        echo "  health - Run health checks"
        echo "  test - Run smoke tests"
        exit 1
        ;;
esac