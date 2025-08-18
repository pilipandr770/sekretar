#!/bin/bash

# Comprehensive monitoring initialization script for AI Secretary
# Sets up all monitoring, alerting, and dashboard components

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

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

# Check if running as root (for some operations)
check_permissions() {
    if [[ $EUID -eq 0 ]]; then
        log_warn "Running as root. Some operations may require different permissions."
    fi
}

# Initialize monitoring infrastructure
init_monitoring_infrastructure() {
    log_step "Initializing monitoring infrastructure..."
    
    # Run monitoring setup
    if [ -f "$SCRIPT_DIR/setup-monitoring.sh" ]; then
        log_info "Running monitoring setup..."
        bash "$SCRIPT_DIR/setup-monitoring.sh" setup
    else
        log_error "setup-monitoring.sh not found"
        exit 1
    fi
}

# Initialize alerting system
init_alerting_system() {
    log_step "Initializing alerting system..."
    
    # Run alerting setup
    if [ -f "$SCRIPT_DIR/setup-alerting.sh" ]; then
        log_info "Running alerting setup..."
        bash "$SCRIPT_DIR/setup-alerting.sh" setup
    else
        log_error "setup-alerting.sh not found"
        exit 1
    fi
}

# Create monitoring environment configuration
create_monitoring_config() {
    log_step "Creating monitoring configuration..."
    
    if [ ! -f "$PROJECT_ROOT/.env.monitoring" ]; then
        cat > "$PROJECT_ROOT/.env.monitoring" << 'EOF'
# AI Secretary Monitoring Configuration

# Monitoring Features
MONITORING_ENABLED=true
ALERTING_ENABLED=true
ERROR_TRACKING_ENABLED=true

# Performance Thresholds
PERFORMANCE_LOG_THRESHOLD_MS=1000
CPU_ALERT_THRESHOLD=85.0
MEMORY_ALERT_THRESHOLD=90.0
DISK_ALERT_THRESHOLD=95.0
ERROR_RATE_THRESHOLD=0.05
RESPONSE_TIME_THRESHOLD=2.0

# Metrics Retention
METRICS_RETENTION_DAYS=30

# Grafana Configuration
GRAFANA_ADMIN_PASSWORD=admin123
GRAFANA_ALLOW_SIGN_UP=false

# Prometheus Configuration
PROMETHEUS_RETENTION_DAYS=30
PROMETHEUS_SCRAPE_INTERVAL=15s

# Email Alerting
ALERTING_EMAIL_ENABLED=false
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_USE_TLS=true
ALERT_FROM_EMAIL=alerts@ai-secretary.com
CRITICAL_ALERT_EMAIL=
WARNING_ALERT_EMAIL=
BUSINESS_ALERT_EMAIL=
EMAIL_MIN_SEVERITY=high

# Slack Alerting
ALERTING_SLACK_ENABLED=false
SLACK_WEBHOOK_URL=
SLACK_ALERT_CHANNEL=#alerts
SLACK_MIN_SEVERITY=medium

# Webhook Alerting
ALERTING_WEBHOOK_ENABLED=false
ALERTING_WEBHOOK_URL=
ALERTING_WEBHOOK_TIMEOUT=10
WEBHOOK_MIN_SEVERITY=low

# PagerDuty Integration
PAGERDUTY_INTEGRATION_KEY=

# Webhook Authentication
WEBHOOK_USERNAME=monitoring
WEBHOOK_PASSWORD=secure-webhook-password
EOF
        
        log_info "Monitoring configuration created at .env.monitoring"
        log_warn "Please update .env.monitoring with your actual values"
    else
        log_info "Monitoring configuration already exists"
    fi
}

# Set up log directories
setup_log_directories() {
    log_step "Setting up log directories..."
    
    local log_dirs=(
        "/var/log/ai-secretary"
        "/var/log/ai-secretary/monitoring"
        "/var/log/ai-secretary/alerts"
        "/var/log/ai-secretary/performance"
    )
    
    for dir in "${log_dirs[@]}"; do
        if [ ! -d "$dir" ]; then
            sudo mkdir -p "$dir" 2>/dev/null || mkdir -p "$dir" 2>/dev/null || {
                log_warn "Could not create $dir, using local directory"
                mkdir -p "$PROJECT_ROOT/logs/$(basename $dir)"
            }
        fi
    done
    
    log_info "Log directories created"
}

# Install monitoring dependencies
install_dependencies() {
    log_step "Installing monitoring dependencies..."
    
    # Check if jq is installed (for JSON processing)
    if ! command -v jq &> /dev/null; then
        log_warn "jq not found. Some monitoring scripts may not work properly."
        log_info "Install jq with: sudo apt-get install jq (Ubuntu/Debian) or brew install jq (macOS)"
    fi
    
    # Check if curl is installed
    if ! command -v curl &> /dev/null; then
        log_error "curl is required but not installed"
        exit 1
    fi
    
    # Check if docker is installed
    if ! command -v docker &> /dev/null; then
        log_error "Docker is required but not installed"
        exit 1
    fi
    
    # Check if docker-compose is installed
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is required but not installed"
        exit 1
    fi
    
    log_info "Dependencies check completed"
}

# Create monitoring scripts
create_monitoring_scripts() {
    log_step "Creating monitoring scripts..."
    
    # Create monitoring wrapper script
    cat > "$PROJECT_ROOT/monitor.sh" << 'EOF'
#!/bin/bash

# AI Secretary Monitoring Wrapper Script
# Provides easy access to all monitoring functions

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-help}" in
    "status")
        echo "AI Secretary System Status"
        echo "========================="
        ./deployment/scripts/performance-monitor.sh report
        ;;
    "health")
        echo "Running health checks..."
        ./deployment/scripts/health-check.sh
        ;;
    "alerts")
        echo "Managing alerts..."
        ./deployment/scripts/manage-alerts.sh "${@:2}"
        ;;
    "test")
        echo "Running monitoring tests..."
        ./deployment/scripts/test-alerts.sh
        ;;
    "logs")
        service="${2:-app}"
        echo "Showing logs for $service..."
        docker-compose -f docker-compose.prod.yml logs -f "$service"
        ;;
    "metrics")
        echo "Fetching metrics..."
        curl -s http://localhost:5000/api/v1/metrics | head -20
        ;;
    "dashboard")
        echo "Opening monitoring dashboard..."
        echo "Grafana: http://localhost:3000"
        echo "Prometheus: http://localhost:9090"
        echo "Alertmanager: http://localhost:9093"
        ;;
    "restart")
        echo "Restarting monitoring services..."
        docker-compose -f docker-compose.prod.yml restart prometheus grafana alertmanager
        ;;
    "help"|*)
        echo "AI Secretary Monitoring Commands"
        echo "==============================="
        echo ""
        echo "Usage: $0 <command> [options]"
        echo ""
        echo "Commands:"
        echo "  status     - Show system status and performance"
        echo "  health     - Run health checks"
        echo "  alerts     - Manage alerts (list, silence, etc.)"
        echo "  test       - Test monitoring and alerting"
        echo "  logs       - Show service logs"
        echo "  metrics    - Show current metrics"
        echo "  dashboard  - Show dashboard URLs"
        echo "  restart    - Restart monitoring services"
        echo "  help       - Show this help message"
        echo ""
        echo "Examples:"
        echo "  $0 status                    # Show system status"
        echo "  $0 alerts list              # List active alerts"
        echo "  $0 logs app                 # Show application logs"
        echo "  $0 test                     # Test alert system"
        ;;
esac
EOF
    
    chmod +x "$PROJECT_ROOT/monitor.sh"
    
    log_info "Monitoring wrapper script created at monitor.sh"
}

# Validate monitoring setup
validate_monitoring_setup() {
    log_step "Validating monitoring setup..."
    
    local validation_errors=0
    
    # Check configuration files
    local required_files=(
        "deployment/prometheus/prometheus.yml"
        "deployment/prometheus/rules/ai-secretary-alerts.yml"
        "deployment/grafana/provisioning/datasources/prometheus.yml"
        "deployment/alertmanager/alertmanager.yml"
    )
    
    for file in "${required_files[@]}"; do
        if [ ! -f "$PROJECT_ROOT/$file" ]; then
            log_error "Required file missing: $file"
            ((validation_errors++))
        fi
    done
    
    # Check scripts
    local required_scripts=(
        "deployment/scripts/setup-monitoring.sh"
        "deployment/scripts/setup-alerting.sh"
        "deployment/scripts/performance-monitor.sh"
        "deployment/scripts/health-check.sh"
    )
    
    for script in "${required_scripts[@]}"; do
        if [ ! -f "$PROJECT_ROOT/$script" ]; then
            log_error "Required script missing: $script"
            ((validation_errors++))
        fi
    done
    
    # Check environment files
    if [ ! -f "$PROJECT_ROOT/.env.monitoring" ]; then
        log_warn "Monitoring environment file not found"
    fi
    
    if [ $validation_errors -eq 0 ]; then
        log_info "Monitoring setup validation passed"
    else
        log_error "Monitoring setup validation failed with $validation_errors errors"
        return 1
    fi
}

# Start monitoring services
start_monitoring_services() {
    log_step "Starting monitoring services..."
    
    cd "$PROJECT_ROOT"
    
    # Load monitoring environment
    if [ -f ".env.monitoring" ]; then
        set -a
        source .env.monitoring
        set +a
    fi
    
    # Start monitoring stack
    docker-compose -f docker-compose.prod.yml up -d prometheus grafana alertmanager node-exporter
    
    # Wait for services to be ready
    log_info "Waiting for services to start..."
    sleep 30
    
    # Check service health
    local services_ready=true
    
    if ! curl -f -s "http://localhost:9090/-/healthy" > /dev/null; then
        log_error "Prometheus is not ready"
        services_ready=false
    fi
    
    if ! curl -f -s "http://localhost:3000/api/health" > /dev/null; then
        log_error "Grafana is not ready"
        services_ready=false
    fi
    
    if ! curl -f -s "http://localhost:9093/-/healthy" > /dev/null; then
        log_error "Alertmanager is not ready"
        services_ready=false
    fi
    
    if [ "$services_ready" = true ]; then
        log_info "All monitoring services are ready"
    else
        log_warn "Some monitoring services may not be ready yet"
    fi
}

# Display setup summary
display_setup_summary() {
    log_step "Monitoring initialization completed!"
    
    echo ""
    echo "Setup Summary:"
    echo "=============="
    echo "✓ Monitoring infrastructure configured"
    echo "✓ Alerting system set up"
    echo "✓ Dashboard provisioning configured"
    echo "✓ Performance monitoring enabled"
    echo "✓ Error tracking initialized"
    echo "✓ Runbooks and scripts created"
    echo ""
    echo "Access Information:"
    echo "=================="
    echo "Grafana Dashboard:    http://localhost:3000 (admin/admin123)"
    echo "Prometheus:           http://localhost:9090"
    echo "Alertmanager:         http://localhost:9093"
    echo "Application Health:   http://localhost:5000/api/v1/health"
    echo "Application Metrics:  http://localhost:5000/api/v1/metrics"
    echo ""
    echo "Quick Commands:"
    echo "==============="
    echo "System Status:        ./monitor.sh status"
    echo "Health Check:         ./monitor.sh health"
    echo "View Alerts:          ./monitor.sh alerts list"
    echo "Test Alerts:          ./monitor.sh test"
    echo "View Logs:            ./monitor.sh logs [service]"
    echo "Restart Monitoring:   ./monitor.sh restart"
    echo ""
    echo "Configuration Files:"
    echo "==================="
    echo "Main Config:          .env.monitoring"
    echo "Prometheus Rules:     deployment/prometheus/rules/"
    echo "Grafana Dashboards:   deployment/grafana/dashboards/"
    echo "Alert Templates:      deployment/alertmanager/templates/"
    echo "Runbooks:             deployment/scripts/runbooks/"
    echo ""
    echo "Next Steps:"
    echo "==========="
    echo "1. Update .env.monitoring with your notification settings"
    echo "2. Configure email/Slack/webhook endpoints for alerts"
    echo "3. Customize alert thresholds for your environment"
    echo "4. Import additional Grafana dashboards if needed"
    echo "5. Test the complete monitoring pipeline"
    echo "6. Set up regular maintenance schedules"
    echo ""
    echo "Documentation:"
    echo "=============="
    echo "Runbooks:             deployment/scripts/runbooks/README.md"
    echo "Incident Response:    deployment/scripts/incident-response.md"
    echo "Performance Guide:    deployment/scripts/performance-monitor.sh help"
    echo ""
}

# Main execution
main() {
    echo "AI Secretary Monitoring Initialization"
    echo "====================================="
    echo ""
    
    check_permissions
    install_dependencies
    setup_log_directories
    create_monitoring_config
    init_monitoring_infrastructure
    init_alerting_system
    create_monitoring_scripts
    validate_monitoring_setup
    
    # Ask if user wants to start services
    read -p "Do you want to start monitoring services now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        start_monitoring_services
    else
        log_info "Monitoring services not started. Use './monitor.sh restart' to start them later."
    fi
    
    display_setup_summary
}

# Handle script arguments
case "${1:-init}" in
    "init")
        main
        ;;
    "validate")
        validate_monitoring_setup
        ;;
    "start")
        start_monitoring_services
        ;;
    "config")
        create_monitoring_config
        ;;
    *)
        echo "Usage: $0 {init|validate|start|config}"
        echo "  init     - Initialize complete monitoring setup (default)"
        echo "  validate - Validate monitoring configuration"
        echo "  start    - Start monitoring services"
        echo "  config   - Create monitoring configuration"
        exit 1
        ;;
esac