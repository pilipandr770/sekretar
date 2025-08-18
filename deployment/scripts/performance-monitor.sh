#!/bin/bash

# Performance monitoring script for AI Secretary
# Provides real-time performance monitoring and alerting

set -e

# Configuration
APP_URL="http://localhost:5000"
PROMETHEUS_URL="http://localhost:9090"
GRAFANA_URL="http://localhost:3000"
CHECK_INTERVAL=30
LOG_FILE="/var/log/ai-secretary-performance.log"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Thresholds
CPU_THRESHOLD=80
MEMORY_THRESHOLD=85
DISK_THRESHOLD=90
RESPONSE_TIME_THRESHOLD=2000  # milliseconds
ERROR_RATE_THRESHOLD=5        # percentage

# Functions
log_message() {
    local level="$1"
    local message="$2"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

log_info() {
    log_message "INFO" "$1"
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    log_message "WARN" "$1"
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    log_message "ERROR" "$1"
    echo -e "${RED}[ERROR]${NC} $1"
}

log_debug() {
    log_message "DEBUG" "$1"
    echo -e "${BLUE}[DEBUG]${NC} $1"
}

# Check system resources
check_system_resources() {
    local cpu_usage=$(top -bn1 | grep "Cpu(s)" | awk '{print $2}' | awk -F'%' '{print $1}')
    local memory_usage=$(free | grep Mem | awk '{printf "%.1f", $3/$2 * 100.0}')
    local disk_usage=$(df -h / | awk 'NR==2{printf "%d", $5}')
    
    # Remove potential decimal points for comparison
    cpu_usage=${cpu_usage%.*}
    memory_usage=${memory_usage%.*}
    
    echo "System Resources:"
    echo "  CPU Usage: ${cpu_usage}%"
    echo "  Memory Usage: ${memory_usage}%"
    echo "  Disk Usage: ${disk_usage}%"
    
    # Check thresholds
    if [ "$cpu_usage" -gt "$CPU_THRESHOLD" ]; then
        log_warn "High CPU usage detected: ${cpu_usage}%"
    fi
    
    if [ "$memory_usage" -gt "$MEMORY_THRESHOLD" ]; then
        log_warn "High memory usage detected: ${memory_usage}%"
    fi
    
    if [ "$disk_usage" -gt "$DISK_THRESHOLD" ]; then
        log_error "High disk usage detected: ${disk_usage}%"
    fi
}

# Check application performance
check_application_performance() {
    local start_time=$(date +%s%3N)
    local http_code=$(curl -o /dev/null -s -w "%{http_code}" "$APP_URL/api/v1/health")
    local end_time=$(date +%s%3N)
    local response_time=$((end_time - start_time))
    
    echo "Application Performance:"
    echo "  Health Check Status: $http_code"
    echo "  Response Time: ${response_time}ms"
    
    if [ "$http_code" != "200" ]; then
        log_error "Application health check failed with status: $http_code"
    fi
    
    if [ "$response_time" -gt "$RESPONSE_TIME_THRESHOLD" ]; then
        log_warn "Slow response time detected: ${response_time}ms"
    fi
}

# Check error rates
check_error_rates() {
    if ! command -v jq &> /dev/null; then
        log_debug "jq not available, skipping error rate check"
        return
    fi
    
    local monitoring_data=$(curl -s "$APP_URL/api/v1/monitoring/status" 2>/dev/null)
    
    if [ $? -eq 0 ] && [ -n "$monitoring_data" ]; then
        local error_rate=$(echo "$monitoring_data" | jq -r '.performance.error_rate // 0')
        
        echo "Error Metrics:"
        echo "  Error Rate: ${error_rate}%"
        
        # Convert to integer for comparison
        error_rate_int=${error_rate%.*}
        
        if [ "$error_rate_int" -gt "$ERROR_RATE_THRESHOLD" ]; then
            log_warn "High error rate detected: ${error_rate}%"
        fi
    else
        log_debug "Could not retrieve error rate data"
    fi
}

# Check database performance
check_database_performance() {
    local db_status=$(docker exec ai_secretary_postgres pg_isready -U postgres 2>/dev/null)
    
    if [ $? -eq 0 ]; then
        echo "Database Status: Ready"
        
        # Check connection count
        local connections=$(docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | xargs)
        
        if [ -n "$connections" ]; then
            echo "  Active Connections: $connections"
            
            if [ "$connections" -gt 50 ]; then
                log_warn "High number of database connections: $connections"
            fi
        fi
        
        # Check for long-running queries
        local long_queries=$(docker exec ai_secretary_postgres psql -U postgres -d ai_secretary -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active' AND now() - query_start > interval '5 minutes';" 2>/dev/null | xargs)
        
        if [ -n "$long_queries" ] && [ "$long_queries" -gt 0 ]; then
            log_warn "Long-running queries detected: $long_queries"
        fi
    else
        log_error "Database is not ready"
    fi
}

# Check Redis performance
check_redis_performance() {
    local redis_status=$(docker exec ai_secretary_redis redis-cli ping 2>/dev/null)
    
    if [ "$redis_status" = "PONG" ]; then
        echo "Redis Status: Ready"
        
        # Check memory usage
        local redis_memory=$(docker exec ai_secretary_redis redis-cli info memory 2>/dev/null | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        
        if [ -n "$redis_memory" ]; then
            echo "  Memory Usage: $redis_memory"
        fi
        
        # Check connected clients
        local redis_clients=$(docker exec ai_secretary_redis redis-cli info clients 2>/dev/null | grep connected_clients | cut -d: -f2 | tr -d '\r')
        
        if [ -n "$redis_clients" ]; then
            echo "  Connected Clients: $redis_clients"
            
            if [ "$redis_clients" -gt 100 ]; then
                log_warn "High number of Redis connections: $redis_clients"
            fi
        fi
    else
        log_error "Redis is not responding"
    fi
}

# Check external API status
check_external_apis() {
    echo "External API Status:"
    
    # Check OpenAI API
    local openai_status=$(curl -o /dev/null -s -w "%{http_code}" "https://api.openai.com/v1/models" -H "Authorization: Bearer dummy" 2>/dev/null)
    echo "  OpenAI API: $openai_status"
    
    # Check Stripe API
    local stripe_status=$(curl -o /dev/null -s -w "%{http_code}" "https://api.stripe.com/v1/account" -H "Authorization: Bearer dummy" 2>/dev/null)
    echo "  Stripe API: $stripe_status"
    
    # Check Google Calendar API
    local google_status=$(curl -o /dev/null -s -w "%{http_code}" "https://www.googleapis.com/calendar/v3/users/me/calendarList" -H "Authorization: Bearer dummy" 2>/dev/null)
    echo "  Google Calendar API: $google_status"
}

# Generate performance report
generate_report() {
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    echo "=================================="
    echo "AI Secretary Performance Report"
    echo "Generated: $timestamp"
    echo "=================================="
    echo ""
    
    check_system_resources
    echo ""
    
    check_application_performance
    echo ""
    
    check_error_rates
    echo ""
    
    check_database_performance
    echo ""
    
    check_redis_performance
    echo ""
    
    check_external_apis
    echo ""
    
    echo "=================================="
    echo "Report Complete"
    echo "=================================="
}

# Continuous monitoring mode
continuous_monitoring() {
    log_info "Starting continuous performance monitoring (interval: ${CHECK_INTERVAL}s)"
    log_info "Log file: $LOG_FILE"
    
    while true; do
        generate_report
        echo ""
        echo "Waiting ${CHECK_INTERVAL} seconds for next check..."
        sleep "$CHECK_INTERVAL"
        clear
    done
}

# Performance benchmark
run_benchmark() {
    echo "Running Performance Benchmark"
    echo "============================="
    
    # Test application endpoints
    local endpoints=(
        "/api/v1/health"
        "/api/v1/health/ready"
        "/api/v1/health/live"
        "/api/v1/metrics"
        "/api/v1/monitoring/status"
    )
    
    for endpoint in "${endpoints[@]}"; do
        echo -n "Testing $endpoint... "
        
        local start_time=$(date +%s%3N)
        local http_code=$(curl -o /dev/null -s -w "%{http_code}" "$APP_URL$endpoint")
        local end_time=$(date +%s%3N)
        local response_time=$((end_time - start_time))
        
        echo "Status: $http_code, Time: ${response_time}ms"
    done
    
    echo ""
    echo "Load Test (10 concurrent requests):"
    
    # Simple load test
    for i in {1..10}; do
        (
            local start_time=$(date +%s%3N)
            curl -o /dev/null -s "$APP_URL/api/v1/health"
            local end_time=$(date +%s%3N)
            local response_time=$((end_time - start_time))
            echo "Request $i: ${response_time}ms"
        ) &
    done
    
    wait
    echo "Load test complete"
}

# Alert simulation
simulate_alerts() {
    echo "Simulating Performance Alerts"
    echo "============================="
    
    # Simulate high CPU alert
    echo "Simulating high CPU usage alert..."
    curl -s -X POST "$APP_URL/api/v1/monitoring/webhooks/alerts" \
        -H "Content-Type: application/json" \
        -d '{
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "HighCPUUsage",
                    "severity": "warning",
                    "instance": "localhost:5000",
                    "component": "system"
                },
                "annotations": {
                    "summary": "High CPU usage detected",
                    "description": "CPU usage is above 85% for the last 5 minutes"
                }
            }]
        }' > /dev/null
    
    echo "High CPU alert sent"
    
    # Simulate application error alert
    echo "Simulating application error alert..."
    curl -s -X POST "$APP_URL/api/v1/monitoring/webhooks/alerts" \
        -H "Content-Type: application/json" \
        -d '{
            "alerts": [{
                "status": "firing",
                "labels": {
                    "alertname": "HighErrorRate",
                    "severity": "critical",
                    "instance": "localhost:5000",
                    "component": "application"
                },
                "annotations": {
                    "summary": "High error rate detected",
                    "description": "Error rate is above 5% for the last 5 minutes"
                }
            }]
        }' > /dev/null
    
    echo "High error rate alert sent"
    echo "Check your configured notification channels for alerts"
}

# Main command handling
case "${1:-report}" in
    "report")
        generate_report
        ;;
    "monitor")
        continuous_monitoring
        ;;
    "benchmark")
        run_benchmark
        ;;
    "alerts")
        simulate_alerts
        ;;
    "system")
        check_system_resources
        ;;
    "app")
        check_application_performance
        ;;
    "database")
        check_database_performance
        ;;
    "redis")
        check_redis_performance
        ;;
    "apis")
        check_external_apis
        ;;
    *)
        echo "Usage: $0 {report|monitor|benchmark|alerts|system|app|database|redis|apis}"
        echo ""
        echo "Commands:"
        echo "  report    - Generate one-time performance report (default)"
        echo "  monitor   - Start continuous monitoring"
        echo "  benchmark - Run performance benchmark tests"
        echo "  alerts    - Simulate performance alerts"
        echo "  system    - Check system resources only"
        echo "  app       - Check application performance only"
        echo "  database  - Check database performance only"
        echo "  redis     - Check Redis performance only"
        echo "  apis      - Check external API status only"
        echo ""
        echo "Configuration:"
        echo "  Check interval: ${CHECK_INTERVAL}s"
        echo "  Log file: $LOG_FILE"
        echo "  CPU threshold: ${CPU_THRESHOLD}%"
        echo "  Memory threshold: ${MEMORY_THRESHOLD}%"
        echo "  Disk threshold: ${DISK_THRESHOLD}%"
        echo "  Response time threshold: ${RESPONSE_TIME_THRESHOLD}ms"
        echo "  Error rate threshold: ${ERROR_RATE_THRESHOLD}%"
        exit 1
        ;;
esac