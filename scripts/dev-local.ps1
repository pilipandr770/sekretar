# Local Development Startup Script
# Запускает приложение в режиме локальной разработки с SQLite

param(
    [switch]$Clean,
    [switch]$Verbose,
    [string]$Port = "5000"
)

Write-Host "Starting AI Secretary - Local Development Mode" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Gray

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables for local development
Write-Host "Setting up local development environment..." -ForegroundColor Yellow

$env:FLASK_APP = "run.py"
$env:FLASK_ENV = "development"
$env:FLASK_DEBUG = "1"

# Force SQLite mode
$env:SQLITE_MODE = "true"
$env:DATABASE_URL = "sqlite:///ai_secretary.db"
$env:TEST_DATABASE_URL = "sqlite:///test_ai_secretary.db"

# Disable external services for local development
$env:REDIS_URL = ""
$env:CELERY_BROKER_URL = ""
$env:CELERY_RESULT_BACKEND = ""
$env:RATE_LIMIT_STORAGE_URL = ""

# Set cache to simple mode
$env:CACHE_TYPE = "simple"

# Enable service detection but with fallbacks
$env:SERVICE_DETECTION_ENABLED = "true"
$env:DATABASE_DETECTION_ENABLED = "true"
$env:SQLITE_FALLBACK_ENABLED = "true"
$env:SIMPLE_CACHE_FALLBACK = "true"

# Set default language
$env:DEFAULT_LANGUAGE = "en"

# Set port
$env:PORT = $Port

# Clean database if requested
if ($Clean) {
    Write-Host "Cleaning local database..." -ForegroundColor Yellow
    if (Test-Path "ai_secretary.db") {
        Remove-Item "ai_secretary.db" -Force
        Write-Host "   Removed ai_secretary.db" -ForegroundColor Gray
    }
    if (Test-Path "instance\ai_secretary.db") {
        Remove-Item "instance\ai_secretary.db" -Force
        Write-Host "   Removed instance\ai_secretary.db" -ForegroundColor Gray
    }
}

# Check if translations are compiled
Write-Host "Checking translation files..." -ForegroundColor Yellow
$translationsOk = $true

$languages = @("en", "de", "uk")
foreach ($lang in $languages) {
    $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
    if (-not (Test-Path $moFile)) {
        Write-Host "   Missing compiled translation for $lang" -ForegroundColor Yellow
        $translationsOk = $false
    } else {
        Write-Host "   $lang translations compiled" -ForegroundColor Gray
    }
}

if (-not $translationsOk) {
    Write-Host "Compiling missing translations..." -ForegroundColor Yellow
    try {
        foreach ($lang in $languages) {
            $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
            if (-not (Test-Path $moFile)) {
                pybabel compile -d app\translations -l $lang
                if ($LASTEXITCODE -eq 0) {
                    Write-Host "   Compiled $lang translations" -ForegroundColor Green
                } else {
                    Write-Host "   Failed to compile $lang translations" -ForegroundColor Red
                }
            }
        }
    } catch {
        Write-Host "   Translation compilation failed, continuing anyway..." -ForegroundColor Yellow
    }
}

# Create necessary directories
Write-Host "Creating necessary directories..." -ForegroundColor Yellow
$directories = @("uploads", "logs", "instance")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
        Write-Host "   Created $dir/" -ForegroundColor Gray
    }
}

# Display configuration summary
Write-Host "Local Development Configuration:" -ForegroundColor Cyan
Write-Host "   Environment: development" -ForegroundColor White
Write-Host "   Database: SQLite (ai_secretary.db)" -ForegroundColor White
Write-Host "   Cache: Simple (in-memory)" -ForegroundColor White
Write-Host "   Port: $Port" -ForegroundColor White
Write-Host "   Debug: Enabled" -ForegroundColor White
Write-Host "   Translations: 3 languages (en, de, uk)" -ForegroundColor White

if ($Verbose) {
    Write-Host "   Redis: Disabled" -ForegroundColor Gray
    Write-Host "   Celery: Disabled" -ForegroundColor Gray
    Write-Host "   Rate Limiting: Disabled" -ForegroundColor Gray
    Write-Host "   Service Detection: Enabled with fallbacks" -ForegroundColor Gray
}

Write-Host "============================================================" -ForegroundColor Gray
Write-Host "Application will be available at: http://localhost:$Port" -ForegroundColor Green
Write-Host "API Documentation: http://localhost:$Port/api/v1/docs" -ForegroundColor Green
Write-Host "Health Check: http://localhost:$Port/api/v1/health" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Gray

# Start the application
Write-Host "Starting application..." -ForegroundColor Green
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

try {
    python run.py
} catch {
    Write-Host "Application failed to start: $_" -ForegroundColor Red
    exit 1
}