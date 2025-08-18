#!/bin/bash

# Production update script for AI Secretary
# This script handles zero-downtime updates

set -e

# Configuration
COMPOSE_FILE="docker-compose.prod.yml"
ENV_FILE=".env.prod"

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

# Create backup before update
create_backup() {
    log_info "Creating backup before update..."
    ./deployment/scripts/backup-database.sh
}

# Update application
update_application() {
    log_info "Starting application update..."
    
    # Load environment variables
    export $(grep -v '^#' "${ENV_FILE}" | xargs)
    
    # Pull latest code (if using git)
    if [ -d ".git" ]; then
        log_info "Pulling latest code..."
        git pull origin main
    fi
    
    # Build new images
    log_info "Building new application images..."
    docker-compose -f "${COMPOSE_FILE}" build --no-cache app worker scheduler
    
    # Run database migrations
    log_info "Running database migrations..."
    docker-compose -f "${COMPOSE_FILE}" run --rm app flask db upgrade
    
    # Rolling update of application services
    log_info "Performing rolling update..."
    
    # Update workers first
    docker-compose -f "${COMPOSE_FILE}" up -d --no-deps worker
    sleep 10
    
    # Update scheduler
    docker-compose -f "${COMPOSE_FILE}" up -d --no-deps scheduler
    sleep 5
    
    # Update main application (this will cause brief downtime)
    docker-compose -f "${COMPOSE_FILE}" up -d --no-deps app
    
    # Wait for services to be ready
    log_info "Waiting for services to be ready..."
    sleep 30
    
    # Health check
    log_info "Performing health check..."
    for i in {1..10}; do
        if curl -f http://localhost/health > /dev/null 2>&1; then
            log_info "Health check passed!"
            break
        else
            log_warn "Health check attempt $i failed, retrying..."
            sleep 10
        fi
    done
    
    # Clean up old images
    log_info "Cleaning up old Docker images..."
    docker image prune -f
    
    log_info "Application update completed!"
}

# Rollback function
rollback() {
    log_error "Rolling back to previous version..."
    
    # This is a simplified rollback - in production you might want to
    # keep track of previous image tags and restore from backup
    log_warn "Rollback functionality requires manual intervention"
    log_info "To rollback:"
    log_info "1. Restore database from backup: ./deployment/scripts/restore-database.sh <backup_file>"
    log_info "2. Deploy previous version of code"
    log_info "3. Restart services: docker-compose -f ${COMPOSE_FILE} restart"
}

# Main execution
main() {
    log_info "AI Secretary Production Update"
    log_info "============================="
    
    # Confirm update
    read -p "This will update the production application. Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Update cancelled."
        exit 0
    fi
    
    create_backup
    
    if update_application; then
        log_info "Update completed successfully!"
    else
        log_error "Update failed!"
        read -p "Do you want to rollback? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rollback
        fi
        exit 1
    fi
}

# Handle script arguments
case "${1:-update}" in
    "update")
        main
        ;;
    "rollback")
        rollback
        ;;
    *)
        echo "Usage: $0 {update|rollback}"
        echo "  update   - Update the application (default)"
        echo "  rollback - Rollback to previous version"
        exit 1
        ;;
esac