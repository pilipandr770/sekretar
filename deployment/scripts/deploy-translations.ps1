# Translation deployment script for production

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("staging", "production")]
    [string]$Environment,
    
    [string]$Version = "latest",
    [switch]$SkipBackup = $false,
    [switch]$Rollback = $false,
    [string]$RollbackVersion = ""
)

Write-Host "AI Secretary Translation Deployment" -ForegroundColor Green
Write-Host "===================================" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Cyan
Write-Host "Version: $Version" -ForegroundColor Cyan

# Configuration
$BACKUP_DIR = "deployment/backups/translations"
$COMPOSE_FILE = if ($Environment -eq "production") { "docker-compose.prod.yml" } else { "docker-compose.staging.yml" }
$SERVICE_NAME = "app"

# Ensure backup directory exists
if (!(Test-Path $BACKUP_DIR)) {
    New-Item -ItemType Directory -Path $BACKUP_DIR -Force | Out-Null
}

function Backup-Translations {
    param([string]$BackupName)
    
    Write-Host "Creating translation backup: $BackupName" -ForegroundColor Yellow
    
    $backupPath = "$BACKUP_DIR/$BackupName"
    if (!(Test-Path $backupPath)) {
        New-Item -ItemType Directory -Path $backupPath -Force | Out-Null
    }
    
    # Copy current translation files
    if (Test-Path "app/translations") {
        Copy-Item -Path "app/translations" -Destination "$backupPath/" -Recurse -Force
        Write-Host "✓ Translation files backed up to $backupPath" -ForegroundColor Green
    }
    
    # Create metadata file
    $metadata = @{
        timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
        environment = $Environment
        version = $Version
        git_commit = (git rev-parse HEAD 2>$null)
        languages = @("en", "de", "uk")
    }
    
    $metadata | ConvertTo-Json | Out-File "$backupPath/metadata.json" -Encoding UTF8
    Write-Host "✓ Backup metadata created" -ForegroundColor Green
}

function Test-Translations {
    Write-Host "Validating translation files..." -ForegroundColor Yellow
    
    $languages = @("en", "de", "uk")
    $valid = $true
    
    foreach ($lang in $languages) {
        $poFile = "app/translations/$lang/LC_MESSAGES/messages.po"
        $moFile = "app/translations/$lang/LC_MESSAGES/messages.mo"
        
        if (!(Test-Path $poFile)) {
            Write-Host "✗ Missing .po file for $lang" -ForegroundColor Red
            $valid = $false
        } else {
            Write-Host "✓ $lang .po file exists" -ForegroundColor Green
        }
        
        if (!(Test-Path $moFile)) {
            Write-Host "✗ Missing .mo file for $lang" -ForegroundColor Red
            $valid = $false
        } else {
            $size = (Get-Item $moFile).Length
            Write-Host "✓ $lang .mo file exists ($size bytes)" -ForegroundColor Green
        }
    }
    
    if (!$valid) {
        Write-Host "Translation validation failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ All translation files validated" -ForegroundColor Green
}

function Invoke-TranslationDeployment {
    Write-Host "Deploying translations to $Environment..." -ForegroundColor Yellow
    
    # Stop services
    Write-Host "Stopping services..." -ForegroundColor Gray
    docker-compose -f $COMPOSE_FILE stop $SERVICE_NAME
    
    # Update translation files in containers
    Write-Host "Updating translation files..." -ForegroundColor Gray
    
    # Rebuild and restart services
    Write-Host "Rebuilding and restarting services..." -ForegroundColor Gray
    docker-compose -f $COMPOSE_FILE up -d --build $SERVICE_NAME
    
    # Wait for services to be healthy
    Write-Host "Waiting for services to be healthy..." -ForegroundColor Gray
    $maxAttempts = 30
    $attempt = 0
    
    do {
        $attempt++
        Start-Sleep 5
        
        $health = docker-compose -f $COMPOSE_FILE ps --format json | ConvertFrom-Json | Where-Object { $_.Service -eq $SERVICE_NAME }
        
        if ($health -and $health.State -eq "running") {
            Write-Host "✓ Service is running" -ForegroundColor Green
            break
        }
        
        Write-Host "Waiting for service... (attempt $attempt/$maxAttempts)" -ForegroundColor Gray
        
    } while ($attempt -lt $maxAttempts)
    
    if ($attempt -ge $maxAttempts) {
        Write-Host "✗ Service failed to start properly" -ForegroundColor Red
        exit 1
    }
}

function Test-Deployment {
    Write-Host "Testing translation deployment..." -ForegroundColor Yellow
    
    # Test API endpoint
    $testUrl = if ($Environment -eq "production") { "https://api.yourdomain.com" } else { "https://staging-api.yourdomain.com" }
    
    try {
        $response = Invoke-RestMethod -Uri "$testUrl/api/v1/languages" -Method GET -TimeoutSec 10
        
        if ($response -and $response.data) {
            $availableLanguages = $response.data
            Write-Host "✓ Available languages: $($availableLanguages -join ', ')" -ForegroundColor Green
        } else {
            Write-Host "✗ Invalid language API response" -ForegroundColor Red
            return $false
        }
    } catch {
        Write-Host "✗ Failed to test language API: $($_.Exception.Message)" -ForegroundColor Red
        return $false
    }
    
    # Test translation endpoint for each language
    $languages = @("en", "de", "uk")
    foreach ($lang in $languages) {
        try {
            $testKey = "Welcome"
            $response = Invoke-RestMethod -Uri "$testUrl/api/v1/translate?key=$testKey`&lang=$lang" -Method GET -TimeoutSec 10
            
            if ($response -and $response.translation) {
                Write-Host "✓ $lang translation test passed: $($response.translation)" -ForegroundColor Green
            } else {
                Write-Host "✗ $lang translation test failed" -ForegroundColor Red
                return $false
            }
        } catch {
            Write-Host "✗ Failed to test $lang translation: $($_.Exception.Message)" -ForegroundColor Red
            return $false
        }
    }
    
    Write-Host "✓ All translation tests passed" -ForegroundColor Green
    return $true
}

function Restore-TranslationDeployment {
    param([string]$RollbackVersion)
    
    Write-Host "Rolling back to version: $RollbackVersion" -ForegroundColor Yellow
    
    $backupPath = "$BACKUP_DIR/$RollbackVersion"
    
    if (!(Test-Path $backupPath)) {
        Write-Host "✗ Backup not found: $backupPath" -ForegroundColor Red
        exit 1
    }
    
    # Restore translation files
    if (Test-Path "$backupPath/translations") {
        Remove-Item -Path "app/translations" -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path "$backupPath/translations" -Destination "app/" -Recurse -Force
        Write-Host "✓ Translation files restored from backup" -ForegroundColor Green
    }
    
    # Redeploy with restored files
    Invoke-TranslationDeployment
    
    Write-Host "✓ Rollback completed" -ForegroundColor Green
}

# Main execution
try {
    if ($Rollback) {
        if (!$RollbackVersion) {
            Write-Host "Rollback version is required for rollback operation" -ForegroundColor Red
            exit 1
        }
        Restore-TranslationDeployment -RollbackVersion $RollbackVersion
    } else {
        # Normal deployment
        $timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
        $backupName = "$Environment-$Version-$timestamp"
        
        # Create backup
        if (!$SkipBackup) {
            Backup-Translations -BackupName $backupName
        }
        
        # Validate translations
        Test-Translations
        
        # Deploy
        Invoke-TranslationDeployment
        
        # Test deployment
        $testPassed = Test-Deployment
        
        if ($testPassed) {
            Write-Host "`n✅ Translation deployment completed successfully!" -ForegroundColor Green
            Write-Host "Environment: $Environment" -ForegroundColor White
            Write-Host "Version: $Version" -ForegroundColor White
            Write-Host "Backup: $backupName" -ForegroundColor White
        } else {
            Write-Host "`n❌ Translation deployment failed tests!" -ForegroundColor Red
            Write-Host "Consider rolling back with:" -ForegroundColor Yellow
            Write-Host "  .\deploy-translations.ps1 -Environment $Environment -Rollback -RollbackVersion $backupName" -ForegroundColor White
            exit 1
        }
    }
} catch {
    Write-Host "`n❌ Deployment failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Stack trace:" -ForegroundColor Gray
    Write-Host $_.ScriptStackTrace -ForegroundColor Gray
    exit 1
}

Write-Host "`nDeployment completed!" -ForegroundColor Green