#!/bin/bash

# Database backup script for AI Secretary
# This script creates backups of the PostgreSQL database

set -e

# Configuration
BACKUP_DIR="/backups"
DB_CONTAINER="ai_secretary_db"
DB_NAME="${POSTGRES_DB:-ai_secretary}"
DB_USER="${POSTGRES_USER:-ai_secretary_user}"
RETENTION_DAYS=30

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Generate backup filename with timestamp
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/ai_secretary_backup_${TIMESTAMP}.sql"

echo "Starting database backup..."
echo "Backup file: ${BACKUP_FILE}"

# Create database backup
docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB_NAME}" --verbose --clean --no-owner --no-privileges > "${BACKUP_FILE}"

# Compress the backup
gzip "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

echo "Database backup completed: ${BACKUP_FILE}"

# Calculate backup size
BACKUP_SIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "Backup size: ${BACKUP_SIZE}"

# Clean up old backups (keep only last RETENTION_DAYS days)
echo "Cleaning up old backups (keeping last ${RETENTION_DAYS} days)..."
find "${BACKUP_DIR}" -name "ai_secretary_backup_*.sql.gz" -type f -mtime +${RETENTION_DAYS} -delete

# List remaining backups
echo "Remaining backups:"
ls -lh "${BACKUP_DIR}"/ai_secretary_backup_*.sql.gz 2>/dev/null || echo "No backups found"

echo "Backup process completed successfully!"