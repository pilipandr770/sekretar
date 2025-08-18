#!/bin/bash

# Production deployment script for AI Secretary
# This script handles the complete deployment process

set -e

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"
BACKUP_DIR="/backups"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if [ ! -f "${ENV_FILE}" ]; then
        log_error "Environment file ${ENV_FILE} not found!"
        log_info "Please run: ./deployment/scripts/generate-secrets.sh"
        exit 1
    fi
    
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "Docker compose file ${COMPOSE_FILE} not found!"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed!"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed!"
        exit 1
    fi
    
    log_info "Prerequisites check passed!"
}

# Create necessary directories
create_directories() {
    log_info "Creating necessary directories..."
    mkdir -p uploads logs evidence/kyb "${BACKUP_DIR}"
    chmod 755 uploads logs evidence/kyb "${BACKUP_DIR}"
}

# Build and deploy
deploy() {
    log_info "Starting deployment..."
    
    # Load environment variables
    export $(grep -v '^#' "${ENV_FILE}" | xargs)
    
    # Pull latest images
    log_info "Pulling latest images..."
    docker-compose -f "${COMPOSE_FILE}" pull
    
    # Build application images
    log_info "Building application images..."
    docker-compose -f "${COMPOSE_FILE}" build --no-cache
    
    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker-compose -f "${COMPOSE_FILE}" up -d db redis
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 30
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "${COMPOSE_FILE}" run --rm app flask db upgrade
    
    # Start all services
    log_info "Starting all services..."
    docker-compose -f "${COMPOSE_FILE}" up -d
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 60
    
    # Health check
    log_info "Performing health check..."
    if curl -f http://localhost/health > /dev/null 2>&1; then
        log_info "Health check passed!"
    else
        log_warn "Health check failed, but deployment may still be starting..."
    fi
    
    log_info "Deployment completed!"
}

# Show status
show_status() {
    log_info "Service status:"
    docker-compose -f "${COMPOSE_FILE}" ps
    
    log_info "Service logs (last 20 lines):"
    docker-compose -f "${COMPOSE_FILE}" logs --tail=20
}

# Main execution
main() {
    log_info "AI Secretary Production Deployment"
    log_info "=================================="
    
    check_prerequisites
    create_directories
    deploy
    show_status
    
    log_info "Deployment process completed!"
    log_info "Access the application at: https://yourdomain.com"
    log_info "Access Grafana at: http://localhost:3000"
    log_info "Access Prometheus at: http://localhost:9090"
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "status")
        show_status
        ;;
    "logs")
        docker-compose -f "${COMPOSE_FILE}" logs -f "${2:-app}"
        ;;
    "stop")
        log_info "Stopping services..."
        docker-compose -f "${COMPOSE_FILE}" stop
        ;;
    "restart")
        log_info "Restarting services..."
        docker-compose -f "${COMPOSE_FILE}" restart
        ;;
    "backup")
        ./deployment/scripts/backup-database.sh
        ;;
    *)
        echo "Usage: $0 {deploy|status|logs|stop|restart|backup}"
        echo "  deploy  - Deploy the application (default)"
        echo "  status  - Show service status"
        echo "  logs    - Show service logs (optionally specify service name)"
        echo "  stop    - Stop all services"
        echo "  restart - Restart all services"
        echo "  backup  - Create database backup"
        exit 1
        ;;
esac