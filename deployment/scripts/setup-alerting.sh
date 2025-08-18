#!/bin/bash

# Advanced alerting setup script for AI Secretary
# Configures Prometheus alerts, Alertmanager, and notification channels

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DEPLOYMENT_DIR="$PROJECT_ROOT/deployment"

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
    
    if [ ! -f "$PROJECT_ROOT/.env.prod" ]; then
        log_error ".env.prod file not found. Please create it first."
        exit 1
    fi
    
    if [ ! -f "$DEPLOYMENT_DIR/prometheus/prometheus.yml" ]; then
        log_error "Prometheus configuration not found. Please run setup-monitoring.sh first."
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Setup Alertmanager configuration
setup_alertmanager_config() {
    log_step "Setting up Alertmanager configuration..."
    
    mkdir -p "$DEPLOYMENT_DIR/alertmanager"
    
    # Load environment variables
    if [ -f "$PROJECT_ROOT/.env.prod" ]; then
        set -a
        source "$PROJECT_ROOT/.env.prod"
        set +a
    fi
    
    cat > "$DEPLOYMENT_DIR/alertmanager/alertmanager.yml" << EOF
global:
  smtp_smarthost: '${SMTP_SERVER:-smtp.gmail.com}:${SMTP_PORT:-587}'
  smtp_from: '${ALERT_FROM_EMAIL:-alerts@ai-secretary.com}'
  smtp_auth_username: '${SMTP_USERNAME:-}'
  smtp_auth_password: '${SMTP_PASSWORD:-}'
  smtp_require_tls: true
  resolve_timeout: 5m

templates:
  - '/etc/alertmanager/templates/*.tmpl'

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
    continue: true
  - match:
      severity: warning
    receiver: 'warning-alerts'
    repeat_interval: 30m
    continue: true
  - match:
      component: business
    receiver: 'business-alerts'
    repeat_interval: 1h

receivers:
- name: 'default'
  webhook_configs:
  - url: 'http://app:5000/api/v1/monitoring/webhooks/alerts'
    send_resolved: true
    http_config:
      basic_auth:
        username: '${WEBHOOK_USERNAME:-monitoring}'
        password: '${WEBHOOK_PASSWORD:-secure-webhook-password}'
    title: 'AI Secretary Alert'
    text: '{{ range .Alerts }}{{ .Annotations.summary }}: {{ .Annotations.description }}{{ end }}'

- name: 'critical-alerts'
  email_configs:
  - to: '${CRITICAL_ALERT_EMAIL:-admin@ai-secretary.com}'
    subject: '[CRITICAL] AI Secretary Alert: {{ .GroupLabels.alertname }}'
    html: |
      <h2>🚨 Critical Alert</h2>
      <p><strong>Alert:</strong> {{ .GroupLabels.alertname }}</p>
      {{ range .Alerts }}
      <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
        <h3>{{ .Annotations.summary }}</h3>
        <p><strong>Description:</strong> {{ .Annotations.description }}</p>
        <p><strong>Severity:</strong> {{ .Labels.severity }}</p>
        <p><strong>Component:</strong> {{ .Labels.component }}</p>
        <p><strong>Instance:</strong> {{ .Labels.instance }}</p>
        <p><strong>Started:</strong> {{ .StartsAt }}</p>
        {{ if .EndsAt }}<p><strong>Ended:</strong> {{ .EndsAt }}</p>{{ end }}
        {{ if .Annotations.runbook_url }}<p><strong>Runbook:</strong> <a href="{{ .Annotations.runbook_url }}">{{ .Annotations.runbook_url }}</a></p>{{ end }}
      </div>
      {{ end }}
    send_resolved: true
  slack_configs:
  - api_url: '${SLACK_WEBHOOK_URL:-}'
    channel: '${SLACK_ALERT_CHANNEL:-#alerts}'
    title: '🚨 [CRITICAL] AI Secretary Alert'
    text: |
      {{ range .Alerts }}
      *Alert:* {{ .Annotations.summary }}
      *Description:* {{ .Annotations.description }}
      *Severity:* {{ .Labels.severity }}
      *Component:* {{ .Labels.component }}
      *Instance:* {{ .Labels.instance }}
      *Started:* {{ .StartsAt }}
      {{ if .Annotations.runbook_url }}*Runbook:* {{ .Annotations.runbook_url }}{{ end }}
      {{ end }}
    send_resolved: true
    color: 'danger'

- name: 'warning-alerts'
  email_configs:
  - to: '${WARNING_ALERT_EMAIL:-warnings@ai-secretary.com}'
    subject: '[WARNING] AI Secretary Alert: {{ .GroupLabels.alertname }}'
    html: |
      <h2>⚠️ Warning Alert</h2>
      <p><strong>Alert:</strong> {{ .GroupLabels.alertname }}</p>
      {{ range .Alerts }}
      <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
        <h3>{{ .Annotations.summary }}</h3>
        <p><strong>Description:</strong> {{ .Annotations.description }}</p>
        <p><strong>Severity:</strong> {{ .Labels.severity }}</p>
        <p><strong>Component:</strong> {{ .Labels.component }}</p>
        <p><strong>Instance:</strong> {{ .Labels.instance }}</p>
        <p><strong>Started:</strong> {{ .StartsAt }}</p>
        {{ if .EndsAt }}<p><strong>Ended:</strong> {{ .EndsAt }}</p>{{ end }}
      </div>
      {{ end }}
    send_resolved: true
  slack_configs:
  - api_url: '${SLACK_WEBHOOK_URL:-}'
    channel: '${SLACK_ALERT_CHANNEL:-#alerts}'
    title: '⚠️ [WARNING] AI Secretary Alert'
    text: |
      {{ range .Alerts }}
      *Alert:* {{ .Annotations.summary }}
      *Description:* {{ .Annotations.description }}
      *Severity:* {{ .Labels.severity }}
      *Component:* {{ .Labels.component }}
      {{ end }}
    send_resolved: true
    color: 'warning'

- name: 'business-alerts'
  email_configs:
  - to: '${BUSINESS_ALERT_EMAIL:-business@ai-secretary.com}'
    subject: '[BUSINESS] AI Secretary Metric Alert: {{ .GroupLabels.alertname }}'
    html: |
      <h2>📊 Business Metric Alert</h2>
      <p><strong>Alert:</strong> {{ .GroupLabels.alertname }}</p>
      {{ range .Alerts }}
      <div style="border: 1px solid #ccc; padding: 10px; margin: 10px 0;">
        <h3>{{ .Annotations.summary }}</h3>
        <p><strong>Description:</strong> {{ .Annotations.description }}</p>
        <p><strong>Started:</strong> {{ .StartsAt }}</p>
      </div>
      {{ end }}
    send_resolved: true

inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'instance']
  - source_match:
      alertname: 'ApplicationDown'
    target_match_re:
      alertname: '(HighErrorRate|HighResponseTime|DatabaseConnectionsHigh)'
    equal: ['instance']
EOF

    log_info "Alertmanager configuration created"
}

# Setup alert templates
setup_alert_templates() {
    log_step "Setting up alert templates..."
    
    mkdir -p "$DEPLOYMENT_DIR/alertmanager/templates"
    
    cat > "$DEPLOYMENT_DIR/alertmanager/templates/default.tmpl" << 'EOF'
{{ define "__subject" }}[{{ .Status | toUpper }}{{ if eq .Status "firing" }}:{{ .Alerts.Firing | len }}{{ end }}] {{ .GroupLabels.SortedPairs.Values | join " " }} {{ if gt (len .CommonLabels) (len .GroupLabels) }}({{ with .CommonLabels.Remove .GroupLabels.Names }}{{ .Values | join " " }}{{ end }}){{ end }}{{ end }}

{{ define "__description" }}{{ end }}

{{ define "__text_alert_list" }}{{ range . }}Labels:
{{ range .Labels.SortedPairs }} - {{ .Name }} = {{ .Value }}
{{ end }}Annotations:
{{ range .Annotations.SortedPairs }} - {{ .Name }} = {{ .Value }}
{{ end }}Source: {{ .GeneratorURL }}
{{ end }}{{ end }}

{{ define "slack.default.title" }}{{ template "__subject" . }}{{ end }}
{{ define "slack.default.text" }}{{ if gt (len .Alerts.Firing) 0 }}**Firing:**
{{ template "__text_alert_list" .Alerts.Firing }}{{ end }}{{ if gt (len .Alerts.Resolved) 0 }}**Resolved:**
{{ template "__text_alert_list" .Alerts.Resolved }}{{ end }}{{ end }}

{{ define "email.default.subject" }}{{ template "__subject" . }}{{ end }}
{{ define "email.default.html" }}
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
<meta name="viewport" content="width=device-width" />
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8" />
<title>{{ template "__subject" . }}</title>
<style>
body { font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; font-size: 14px; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; }
.header { background: #f8f9fa; padding: 20px; border-bottom: 1px solid #dee2e6; }
.alert { margin: 20px 0; padding: 15px; border-left: 4px solid #007bff; background: #f8f9fa; }
.alert.firing { border-left-color: #dc3545; background: #f8d7da; }
.alert.resolved { border-left-color: #28a745; background: #d4edda; }
.footer { margin-top: 30px; padding-top: 20px; border-top: 1px solid #dee2e6; font-size: 12px; color: #6c757d; }
</style>
</head>
<body>
<div class="header">
<h1>AI Secretary Alert Notification</h1>
<p>{{ template "__subject" . }}</p>
</div>

{{ if gt (len .Alerts.Firing) 0 }}
<h2>🔥 Firing Alerts</h2>
{{ range .Alerts.Firing }}
<div class="alert firing">
<h3>{{ .Annotations.summary }}</h3>
<p><strong>Description:</strong> {{ .Annotations.description }}</p>
<p><strong>Severity:</strong> {{ .Labels.severity }}</p>
<p><strong>Component:</strong> {{ .Labels.component }}</p>
<p><strong>Instance:</strong> {{ .Labels.instance }}</p>
<p><strong>Started:</strong> {{ .StartsAt }}</p>
{{ if .Annotations.runbook_url }}<p><strong>Runbook:</strong> <a href="{{ .Annotations.runbook_url }}">{{ .Annotations.runbook_url }}</a></p>{{ end }}
</div>
{{ end }}
{{ end }}

{{ if gt (len .Alerts.Resolved) 0 }}
<h2>✅ Resolved Alerts</h2>
{{ range .Alerts.Resolved }}
<div class="alert resolved">
<h3>{{ .Annotations.summary }}</h3>
<p><strong>Description:</strong> {{ .Annotations.description }}</p>
<p><strong>Resolved:</strong> {{ .EndsAt }}</p>
</div>
{{ end }}
{{ end }}

<div class="footer">
<p>This alert was generated by AI Secretary monitoring system.</p>
<p>For more information, visit the <a href="http://localhost:3000">Grafana Dashboard</a> or <a href="http://localhost:9093">Alertmanager</a>.</p>
</div>
</body>
</html>
{{ end }}
EOF

    log_info "Alert templates created"
}

# Setup PagerDuty integration (optional)
setup_pagerduty_integration() {
    log_step "Setting up PagerDuty integration..."
    
    if [ -n "${PAGERDUTY_INTEGRATION_KEY:-}" ]; then
        cat >> "$DEPLOYMENT_DIR/alertmanager/alertmanager.yml" << EOF

- name: 'pagerduty-critical'
  pagerduty_configs:
  - routing_key: '${PAGERDUTY_INTEGRATION_KEY}'
    description: '{{ .GroupLabels.alertname }}: {{ range .Alerts }}{{ .Annotations.summary }}{{ end }}'
    severity: '{{ .CommonLabels.severity }}'
    details:
      firing: '{{ template "__text_alert_list" .Alerts.Firing }}'
      resolved: '{{ template "__text_alert_list" .Alerts.Resolved }}'
      num_firing: '{{ .Alerts.Firing | len }}'
      num_resolved: '{{ .Alerts.Resolved | len }}'
EOF
        
        # Update routes to include PagerDuty for critical alerts
        sed -i '/receiver: '\''critical-alerts'\''/a\    - receiver: '\''pagerduty-critical'\''' "$DEPLOYMENT_DIR/alertmanager/alertmanager.yml"
        
        log_info "PagerDuty integration configured"
    else
        log_warn "PAGERDUTY_INTEGRATION_KEY not set, skipping PagerDuty integration"
    fi
}

# Create alert testing script
create_alert_test_script() {
    log_step "Creating alert testing script..."
    
    cat > "$PROJECT_ROOT/deployment/scripts/test-alerts.sh" << 'EOF'
#!/bin/bash

# Alert testing script for AI Secretary

set -e

APP_URL="http://localhost:5000"
ALERTMANAGER_URL="http://localhost:9093"

echo "AI Secretary Alert Testing"
echo "========================="

# Test webhook endpoint
echo -n "Testing alert webhook endpoint... "
if curl -f -s -X POST "$APP_URL/api/v1/monitoring/webhooks/alerts" \
   -H "Content-Type: application/json" \
   -d '{"alerts":[{"status":"firing","labels":{"alertname":"TestAlert","severity":"warning"},"annotations":{"summary":"Test alert","description":"This is a test alert"}}]}' > /dev/null; then
    echo "PASS"
else
    echo "FAIL"
fi

# Test Alertmanager API
echo -n "Testing Alertmanager API... "
if curl -f -s "$ALERTMANAGER_URL/api/v1/status" | grep -q "ready"; then
    echo "PASS"
else
    echo "FAIL"
fi

# Send test alert to Alertmanager
echo -n "Sending test alert... "
if curl -f -s -X POST "$ALERTMANAGER_URL/api/v1/alerts" \
   -H "Content-Type: application/json" \
   -d '[{
     "labels": {
       "alertname": "TestAlert",
       "severity": "warning",
       "instance": "test-instance",
       "component": "test"
     },
     "annotations": {
       "summary": "Test alert from script",
       "description": "This is a test alert generated by the test script"
     },
     "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
     "generatorURL": "http://localhost/test"
   }]' > /dev/null; then
    echo "PASS"
else
    echo "FAIL"
fi

echo ""
echo "Test alert sent! Check your configured notification channels."
echo "You can view active alerts at: $ALERTMANAGER_URL"
EOF

    chmod +x "$PROJECT_ROOT/deployment/scripts/test-alerts.sh"
    
    log_info "Alert testing script created"
}

# Create alert management script
create_alert_management_script() {
    log_step "Creating alert management script..."
    
    cat > "$PROJECT_ROOT/deployment/scripts/manage-alerts.sh" << 'EOF'
#!/bin/bash

# Alert management script for AI Secretary

set -e

ALERTMANAGER_URL="http://localhost:9093"

# Functions
list_alerts() {
    echo "Active Alerts:"
    echo "=============="
    curl -s "$ALERTMANAGER_URL/api/v1/alerts" | jq -r '.data[] | select(.status.state == "active") | "\(.labels.alertname) - \(.labels.severity) - \(.annotations.summary)"'
}

silence_alert() {
    local alertname="$1"
    local duration="${2:-1h}"
    
    if [ -z "$alertname" ]; then
        echo "Usage: $0 silence <alertname> [duration]"
        exit 1
    fi
    
    local end_time=$(date -u -d "+$duration" +%Y-%m-%dT%H:%M:%S.%3NZ)
    
    curl -s -X POST "$ALERTMANAGER_URL/api/v1/silences" \
        -H "Content-Type: application/json" \
        -d '{
            "matchers": [
                {
                    "name": "alertname",
                    "value": "'$alertname'",
                    "isRegex": false
                }
            ],
            "startsAt": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
            "endsAt": "'$end_time'",
            "createdBy": "alert-management-script",
            "comment": "Silenced via management script"
        }' | jq -r '.silenceID // "Failed to create silence"'
}

list_silences() {
    echo "Active Silences:"
    echo "==============="
    curl -s "$ALERTMANAGER_URL/api/v1/silences" | jq -r '.data[] | select(.status.state == "active") | "\(.id) - \(.matchers[0].value) - \(.comment)"'
}

delete_silence() {
    local silence_id="$1"
    
    if [ -z "$silence_id" ]; then
        echo "Usage: $0 delete-silence <silence_id>"
        exit 1
    fi
    
    curl -s -X DELETE "$ALERTMANAGER_URL/api/v1/silence/$silence_id"
    echo "Silence $silence_id deleted"
}

# Main command handling
case "${1:-list}" in
    "list")
        list_alerts
        ;;
    "silence")
        silence_alert "$2" "$3"
        ;;
    "silences")
        list_silences
        ;;
    "delete-silence")
        delete_silence "$2"
        ;;
    "status")
        curl -s "$ALERTMANAGER_URL/api/v1/status" | jq .
        ;;
    *)
        echo "Usage: $0 {list|silence|silences|delete-silence|status}"
        echo "  list - List active alerts"
        echo "  silence <alertname> [duration] - Silence an alert (default: 1h)"
        echo "  silences - List active silences"
        echo "  delete-silence <silence_id> - Delete a silence"
        echo "  status - Show Alertmanager status"
        exit 1
        ;;
esac
EOF

    chmod +x "$PROJECT_ROOT/deployment/scripts/manage-alerts.sh"
    
    log_info "Alert management script created"
}

# Update environment file with alerting variables
update_env_file() {
    log_step "Updating environment file with alerting configuration..."
    
    if [ ! -f "$PROJECT_ROOT/.env.alerting" ]; then
        cat > "$PROJECT_ROOT/.env.alerting" << 'EOF'
# Alerting Configuration for AI Secretary

# Email Settings
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=your-app-password
ALERT_FROM_EMAIL=alerts@yourdomain.com

# Alert Recipients
CRITICAL_ALERT_EMAIL=critical@yourdomain.com
WARNING_ALERT_EMAIL=warnings@yourdomain.com
BUSINESS_ALERT_EMAIL=business@yourdomain.com

# Slack Integration
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/SLACK/WEBHOOK
SLACK_ALERT_CHANNEL=#alerts

# Webhook Authentication
WEBHOOK_USERNAME=monitoring
WEBHOOK_PASSWORD=secure-webhook-password

# PagerDuty Integration (optional)
PAGERDUTY_INTEGRATION_KEY=your-pagerduty-integration-key

# Alert Thresholds (optional overrides)
CPU_ALERT_THRESHOLD=85
MEMORY_ALERT_THRESHOLD=90
DISK_ALERT_THRESHOLD=95
ERROR_RATE_THRESHOLD=0.05
RESPONSE_TIME_THRESHOLD=2.0
EOF
        
        log_info "Alerting environment file created at .env.alerting"
        log_warn "Please update .env.alerting with your actual configuration values"
    else
        log_info "Alerting environment file already exists"
    fi
}

# Validate alerting configuration
validate_configuration() {
    log_step "Validating alerting configuration..."
    
    # Check if Prometheus is running
    if ! curl -f -s "http://localhost:9090/-/healthy" > /dev/null; then
        log_warn "Prometheus is not running or not accessible"
    else
        log_info "Prometheus is accessible"
    fi
    
    # Check if alert rules are loaded
    if curl -s "http://localhost:9090/api/v1/rules" | grep -q "ai-secretary"; then
        log_info "Alert rules are loaded in Prometheus"
    else
        log_warn "Alert rules may not be loaded properly"
    fi
    
    # Validate Alertmanager config
    if [ -f "$DEPLOYMENT_DIR/alertmanager/alertmanager.yml" ]; then
        log_info "Alertmanager configuration file exists"
    else
        log_error "Alertmanager configuration file not found"
    fi
}

# Display setup summary
display_summary() {
    log_step "Alerting setup completed!"
    
    echo ""
    echo "Configuration Summary:"
    echo "====================="
    echo "Alert Rules:          deployment/prometheus/rules/ai-secretary-alerts.yml"
    echo "Alertmanager Config:  deployment/alertmanager/alertmanager.yml"
    echo "Alert Templates:      deployment/alertmanager/templates/"
    echo "Environment Config:   .env.alerting"
    echo ""
    echo "Management Scripts:"
    echo "=================="
    echo "Test Alerts:          ./deployment/scripts/test-alerts.sh"
    echo "Manage Alerts:        ./deployment/scripts/manage-alerts.sh"
    echo ""
    echo "Access URLs:"
    echo "==========="
    echo "Alertmanager:         http://localhost:9093"
    echo "Prometheus Rules:     http://localhost:9090/rules"
    echo "Prometheus Alerts:    http://localhost:9090/alerts"
    echo ""
    echo "Next Steps:"
    echo "=========="
    echo "1. Update .env.alerting with your notification settings"
    echo "2. Restart monitoring services to load new configuration"
    echo "3. Test alerts using: ./deployment/scripts/test-alerts.sh"
    echo "4. Configure notification channels in your email/Slack/PagerDuty"
    echo "5. Review and customize alert thresholds as needed"
    echo ""
    echo "Restart Command:"
    echo "==============="
    echo "docker-compose -f docker-compose.prod.yml restart prometheus alertmanager"
    echo ""
}

# Main execution
main() {
    echo "AI Secretary Alerting Setup"
    echo "=========================="
    echo ""
    
    check_prerequisites
    setup_alertmanager_config
    setup_alert_templates
    setup_pagerduty_integration
    create_alert_test_script
    create_alert_management_script
    update_env_file
    validate_configuration
    display_summary
}

# Handle script arguments
case "${1:-setup}" in
    "setup")
        main
        ;;
    "test")
        "$PROJECT_ROOT/deployment/scripts/test-alerts.sh"
        ;;
    "manage")
        shift
        "$PROJECT_ROOT/deployment/scripts/manage-alerts.sh" "$@"
        ;;
    "validate")
        validate_configuration
        ;;
    *)
        echo "Usage: $0 {setup|test|manage|validate}"
        echo "  setup - Set up alerting configuration (default)"
        echo "  test - Test alert system"
        echo "  manage - Manage alerts (list, silence, etc.)"
        echo "  validate - Validate alerting configuration"
        exit 1
        ;;
esac