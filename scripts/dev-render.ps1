# Render Deployment Startup Script
# Запускает приложение в режиме для развертывания на Render.com с PostgreSQL

param(
    [switch]$Verbose,
    [string]$Port = "5000"
)

Write-Host "Starting AI Secretary - Render Deployment Mode" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Gray

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & ".\.venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables for Render deployment
Write-Host "Setting up Render deployment environment..." -ForegroundColor Yellow

$env:FLASK_APP = "run.py"
$env:FLASK_ENV = "production"
$env:FLASK_DEBUG = "0"

# Force PostgreSQL mode (Render will provide DATABASE_URL)
$env:SQLITE_MODE = "false"

# Enable external services for production
$env:SERVICE_DETECTION_ENABLED = "true"
$env:DATABASE_DETECTION_ENABLED = "true"
$env:POSTGRESQL_FALLBACK_ENABLED = "true"
$env:CACHE_DETECTION_ENABLED = "true"
$env:REDIS_FALLBACK_ENABLED = "true"

# Set cache to Redis mode (Render will provide REDIS_URL)
$env:CACHE_TYPE = "redis"

# Enable configuration validation
$env:CONFIG_VALIDATION_ENABLED = "true"
$env:CONFIG_VALIDATION_STRICT = "false"

# Set default language
$env:DEFAULT_LANGUAGE = "en"

# Set port (Render will override this)
$env:PORT = $Port

# Check required environment variables for Render
Write-Host "Checking Render environment variables..." -ForegroundColor Yellow
$requiredVars = @(
    "DATABASE_URL",
    "SECRET_KEY", 
    "JWT_SECRET_KEY"
)

$missingVars = @()
foreach ($var in $requiredVars) {
    if (-not (Get-Item "env:$var" -ErrorAction SilentlyContinue)) {
        $missingVars += $var
        Write-Host "   Missing: $var" -ForegroundColor Yellow
    } else {
        Write-Host "   Found: $var" -ForegroundColor Gray
    }
}

if ($missingVars.Count -gt 0) {
    Write-Host "Warning: Missing environment variables for Render deployment:" -ForegroundColor Yellow
    foreach ($var in $missingVars) {
        Write-Host "   - $var" -ForegroundColor White
    }
    Write-Host "   These should be set in Render dashboard or .env file" -ForegroundColor Gray
}

# Check optional environment variables
Write-Host "Checking optional services..." -ForegroundColor Yellow
$optionalVars = @{
    "REDIS_URL" = "Redis Cache"
    "OPENAI_API_KEY" = "OpenAI Integration"
    "STRIPE_SECRET_KEY" = "Stripe Billing"
    "GOOGLE_CLIENT_ID" = "Google OAuth"
    "TELEGRAM_BOT_TOKEN" = "Telegram Bot"
}

foreach ($var in $optionalVars.Keys) {
    if (Get-Item "env:$var" -ErrorAction SilentlyContinue) {
        Write-Host "   $($optionalVars[$var]): Configured" -ForegroundColor Gray
    } else {
        Write-Host "   $($optionalVars[$var]): Not configured" -ForegroundColor Yellow
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
Write-Host "Render Deployment Configuration:" -ForegroundColor Cyan
Write-Host "   Environment: production" -ForegroundColor White
Write-Host "   Database: PostgreSQL (from DATABASE_URL)" -ForegroundColor White
Write-Host "   Cache: Redis (from REDIS_URL)" -ForegroundColor White
Write-Host "   Port: $Port (Render will override)" -ForegroundColor White
Write-Host "   Debug: Disabled" -ForegroundColor White
Write-Host "   Translations: 3 languages (en, de, uk)" -ForegroundColor White

if ($Verbose) {
    Write-Host "   Service Detection: Enabled" -ForegroundColor Gray
    Write-Host "   PostgreSQL Fallback: Enabled" -ForegroundColor Gray
    Write-Host "   Redis Fallback: Enabled" -ForegroundColor Gray
    Write-Host "   Config Validation: Enabled (non-strict)" -ForegroundColor Gray
}

Write-Host "============================================================" -ForegroundColor Gray
Write-Host "Application will be available at: http://localhost:$Port" -ForegroundColor Green
Write-Host "API Documentation: http://localhost:$Port/api/v1/docs" -ForegroundColor Green
Write-Host "Health Check: http://localhost:$Port/api/v1/health" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Gray

# Additional Render-specific information
Write-Host "Render Deployment Notes:" -ForegroundColor Cyan
Write-Host "   1. Set environment variables in Render dashboard" -ForegroundColor White
Write-Host "   2. DATABASE_URL will be provided by Render PostgreSQL" -ForegroundColor White
Write-Host "   3. REDIS_URL should be provided by Render Redis" -ForegroundColor White
Write-Host "   4. Build command: pip install -r requirements.txt" -ForegroundColor White
Write-Host "   5. Start command: python run.py" -ForegroundColor White
Write-Host "============================================================" -ForegroundColor Gray

# Start the application
Write-Host "Starting application..." -ForegroundColor Green
Write-Host "   Press Ctrl+C to stop" -ForegroundColor Gray
Write-Host ""

try {
    python run.py
} catch {
    Write-Host "Application failed to start: $_" -ForegroundColor Red
    Write-Host "Check environment variables and database connection" -ForegroundColor Yellow
    exit 1
}