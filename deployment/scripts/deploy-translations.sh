#!/bin/bash
# Translation deployment script for production (Linux/macOS)

set -e

# Parse command line arguments
ENVIRONMENT=""
VERSION="latest"
SKIP_BACKUP=false
ROLLBACK=false
ROLLBACK_VERSION=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -v|--version)
            VERSION="$2"
            shift 2
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --rollback)
            ROLLBACK=true
            shift
            ;;
        --rollback-version)
            ROLLBACK_VERSION="$2"
            shift 2
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

if [ -z "$ENVIRONMENT" ]; then
    echo "Environment is required. Use: staging or production"
    exit 1
fi

if [ "$ENVIRONMENT" != "staging" ] && [ "$ENVIRONMENT" != "production" ]; then
    echo "Invalid environment. Use: staging or production"
    exit 1
fi

echo "AI Secretary Translation Deployment"
echo "==================================="
echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"

# Configuration
BACKUP_DIR="deployment/backups/translations"
COMPOSE_FILE="docker-compose.prod.yml"
if [ "$ENVIRONMENT" = "staging" ]; then
    COMPOSE_FILE="docker-compose.staging.yml"
fi
SERVICE_NAME="app"

# Ensure backup directory exists
mkdir -p "$BACKUP_DIR"

backup_translations() {
    local backup_name="$1"
    
    echo "Creating translation backup: $backup_name"
    
    local backup_path="$BACKUP_DIR/$backup_name"
    mkdir -p "$backup_path"
    
    # Copy current translation files
    if [ -d "app/translations" ]; then
        cp -r app/translations "$backup_path/"
        echo "✓ Translation files backed up to $backup_path"
    fi
    
    # Create metadata file
    cat > "$backup_path/metadata.json" << EOF
{
    "timestamp": "$(date '+%Y-%m-%d %H:%M:%S')",
    "environment": "$ENVIRONMENT",
    "version": "$VERSION",
    "git_commit": "$(git rev-parse HEAD 2>/dev/null || echo 'unknown')",
    "languages": ["en", "de", "uk"]
}
EOF
    echo "✓ Backup metadata created"
}

validate_translations() {
    echo "Validating translation files..."
    
    local languages=("en" "de" "uk")
    local valid=true
    
    for lang in "${languages[@]}"; do
        local po_file="app/translations/$lang/LC_MESSAGES/messages.po"
        local mo_file="app/translations/$lang/LC_MESSAGES/messages.mo"
        
        if [ ! -f "$po_file" ]; then
            echo "✗ Missing .po file for $lang"
            valid=false
        else
            echo "✓ $lang .po file exists"
        fi
        
        if [ ! -f "$mo_file" ]; then
            echo "✗ Missing .mo file for $lang"
            valid=false
        else
            local size=$(stat -c%s "$mo_file" 2>/dev/null || stat -f%z "$mo_file")
            echo "✓ $lang .mo file exists ($size bytes)"
        fi
    done
    
    if [ "$valid" = false ]; then
        echo "Translation validation failed!"
        exit 1
    fi
    
    echo "✓ All translation files validated"
}

deploy_translations() {
    echo "Deploying translations to $ENVIRONMENT..."
    
    # Stop services
    echo "Stopping services..."
    docker-compose -f "$COMPOSE_FILE" stop "$SERVICE_NAME"
    
    # Update translation files in containers
    echo "Updating translation files..."
    
    # Rebuild and restart services
    echo "Rebuilding and restarting services..."
    docker-compose -f "$COMPOSE_FILE" up -d --build "$SERVICE_NAME"
    
    # Wait for services to be healthy
    echo "Waiting for services to be healthy..."
    local max_attempts=30
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        attempt=$((attempt + 1))
        sleep 5
        
        local health=$(docker-compose -f "$COMPOSE_FILE" ps --format json | jq -r ".[] | select(.Service == \"$SERVICE_NAME\") | .State")
        
        if [ "$health" = "running" ]; then
            echo "✓ Service is running"
            break
        fi
        
        echo "Waiting for service... (attempt $attempt/$max_attempts)"
    done
    
    if [ $attempt -ge $max_attempts ]; then
        echo "✗ Service failed to start properly"
        exit 1
    fi
}

test_deployment() {
    echo "Testing translation deployment..."
    
    # Test API endpoint
    local test_url
    if [ "$ENVIRONMENT" = "production" ]; then
        test_url="https://api.yourdomain.com"
    else
        test_url="https://staging-api.yourdomain.com"
    fi
    
    # Test languages endpoint
    if ! response=$(curl -s --max-time 10 "$test_url/api/v1/languages"); then
        echo "✗ Failed to test language API"
        return 1
    fi
    
    if echo "$response" | jq -e '.data' > /dev/null 2>&1; then
        local languages=$(echo "$response" | jq -r '.data | join(", ")')
        echo "✓ Available languages: $languages"
    else
        echo "✗ Invalid language API response"
        return 1
    fi
    
    # Test translation endpoint for each language
    local languages=("en" "de" "uk")
    for lang in "${languages[@]}"; do
        local test_key="Welcome"
        if response=$(curl -s --max-time 10 "$test_url/api/v1/translate?key=$test_key&lang=$lang"); then
            if echo "$response" | jq -e '.translation' > /dev/null 2>&1; then
                local translation=$(echo "$response" | jq -r '.translation')
                echo "✓ $lang translation test passed: $translation"
            else
                echo "✗ $lang translation test failed"
                return 1
            fi
        else
            echo "✗ Failed to test $lang translation"
            return 1
        fi
    done
    
    echo "✓ All translation tests passed"
    return 0
}

rollback_deployment() {
    local rollback_version="$1"
    
    echo "Rolling back to version: $rollback_version"
    
    local backup_path="$BACKUP_DIR/$rollback_version"
    
    if [ ! -d "$backup_path" ]; then
        echo "✗ Backup not found: $backup_path"
        exit 1
    fi
    
    # Restore translation files
    if [ -d "$backup_path/translations" ]; then
        rm -rf app/translations
        cp -r "$backup_path/translations" app/
        echo "✓ Translation files restored from backup"
    fi
    
    # Redeploy with restored files
    deploy_translations
    
    echo "✓ Rollback completed"
}

# Main execution
if [ "$ROLLBACK" = true ]; then
    if [ -z "$ROLLBACK_VERSION" ]; then
        echo "Rollback version is required for rollback operation"
        exit 1
    fi
    rollback_deployment "$ROLLBACK_VERSION"
else
    # Normal deployment
    timestamp=$(date '+%Y%m%d-%H%M%S')
    backup_name="$ENVIRONMENT-$VERSION-$timestamp"
    
    # Create backup
    if [ "$SKIP_BACKUP" = false ]; then
        backup_translations "$backup_name"
    fi
    
    # Validate translations
    validate_translations
    
    # Deploy
    deploy_translations
    
    # Test deployment
    if test_deployment; then
        echo ""
        echo "✅ Translation deployment completed successfully!"
        echo "Environment: $ENVIRONMENT"
        echo "Version: $VERSION"
        echo "Backup: $backup_name"
    else
        echo ""
        echo "❌ Translation deployment failed tests!"
        echo "Consider rolling back with:"
        echo "  ./deploy-translations.sh -e $ENVIRONMENT --rollback --rollback-version $backup_name"
        exit 1
    fi
fi

echo ""
echo "Deployment completed!"