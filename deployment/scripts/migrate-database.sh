#!/bin/bash

# Database migration script for AI Secretary
# This script runs database migrations safely in production

set -e

DB_CONTAINER="ai_secretary_app"
BACKUP_DIR="/backups"

echo "Starting database migration process..."

# Create backup before migration
echo "Creating backup before migration..."
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/pre_migration_backup_${TIMESTAMP}.sql"

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Create backup
docker exec ai_secretary_db pg_dump -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" --verbose --clean --no-owner --no-privileges > "${BACKUP_FILE}"
gzip "${BACKUP_FILE}"

echo "Backup created: ${BACKUP_FILE}.gz"

# Run migrations
echo "Running database migrations..."
docker exec "${DB_CONTAINER}" flask db upgrade

# Verify migration
echo "Verifying migration..."
docker exec "${DB_CONTAINER}" flask db current

echo "Database migration completed successfully!"
echo "Backup available at: ${BACKUP_FILE}.gz"