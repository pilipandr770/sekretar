#!/bin/bash

# Database restore script for AI Secretary
# This script restores the PostgreSQL database from a backup

set -e

# Check if backup file is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <backup_file>"
    echo "Example: $0 /backups/ai_secretary_backup_20240101_120000.sql.gz"
    exit 1
fi

BACKUP_FILE="$1"
DB_CONTAINER="ai_secretary_db"
DB_NAME="${POSTGRES_DB:-ai_secretary}"
DB_USER="${POSTGRES_USER:-ai_secretary_user}"

# Check if backup file exists
if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Error: Backup file '${BACKUP_FILE}' not found!"
    exit 1
fi

echo "Starting database restore..."
echo "Backup file: ${BACKUP_FILE}"
echo "Database: ${DB_NAME}"
echo "User: ${DB_USER}"

# Confirm restore operation
read -p "This will overwrite the current database. Are you sure? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Restore cancelled."
    exit 1
fi

# Stop application containers to prevent connections
echo "Stopping application containers..."
docker-compose -f docker-compose.prod.yml stop app worker scheduler

# Wait for connections to close
sleep 5

# Restore database
echo "Restoring database..."
if [[ "${BACKUP_FILE}" == *.gz ]]; then
    # Compressed backup
    gunzip -c "${BACKUP_FILE}" | docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}"
else
    # Uncompressed backup
    docker exec -i "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" < "${BACKUP_FILE}"
fi

echo "Database restore completed!"

# Start application containers
echo "Starting application containers..."
docker-compose -f docker-compose.prod.yml start app worker scheduler

echo "Restore process completed successfully!"
echo "Please verify that the application is working correctly."