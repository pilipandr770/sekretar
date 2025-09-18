#!/bin/sh
# Translation backup script

set -e

BACKUP_DIR="/backup/translations"
SOURCE_DIR="/source/translations"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="translations_backup_$TIMESTAMP"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

echo "Starting translation backup: $BACKUP_NAME"

# Create backup directory
mkdir -p "$BACKUP_DIR/$BACKUP_NAME"

# Copy translation files
if [ -d "$SOURCE_DIR" ]; then
    rsync -av "$SOURCE_DIR/" "$BACKUP_DIR/$BACKUP_NAME/"
    echo "Translation files backed up successfully"
else
    echo "Source directory not found: $SOURCE_DIR"
    exit 1
fi

# Create metadata file
cat > "$BACKUP_DIR/$BACKUP_NAME/metadata.json" << EOF
{
    "timestamp": "$(date -Iseconds)",
    "backup_name": "$BACKUP_NAME",
    "source_directory": "$SOURCE_DIR",
    "languages": ["en", "de", "uk"],
    "retention_days": $RETENTION_DAYS
}
EOF

# Compress backup
cd "$BACKUP_DIR"
tar -czf "$BACKUP_NAME.tar.gz" "$BACKUP_NAME"
rm -rf "$BACKUP_NAME"

echo "Backup compressed: $BACKUP_NAME.tar.gz"

# Clean up old backups
find "$BACKUP_DIR" -name "translations_backup_*.tar.gz" -mtime +$RETENTION_DAYS -delete
echo "Old backups cleaned up (retention: $RETENTION_DAYS days)"

# Log backup completion
echo "Translation backup completed successfully: $BACKUP_NAME.tar.gz"