# AI Secretary Development Setup Script

param(
    [switch]$SkipVenv,
    [switch]$SkipDocker,
    [switch]$SkipMigrations
)

Write-Host "🚀 AI Secretary Development Setup" -ForegroundColor Green
Write-Host "=================================" -ForegroundColor Green

# Check if Python 3.11 is available
try {
    $pythonVersion = python --version 2>&1
    if ($pythonVersion -notmatch "Python 3\.11") {
        Write-Host "⚠️  Warning: Python 3.11 recommended, found: $pythonVersion" -ForegroundColor Yellow
    } else {
        Write-Host "✅ Python version: $pythonVersion" -ForegroundColor Green
    }
} catch {
    Write-Host "❌ Python not found. Please install Python 3.11" -ForegroundColor Red
    exit 1
}

# Step 1: Setup Virtual Environment
if (-not $SkipVenv) {
    Write-Host "`n📦 Setting up virtual environment..." -ForegroundColor Cyan
    
    if (-not (Test-Path "venv")) {
        Write-Host "Creating virtual environment..." -ForegroundColor Yellow
        python -m venv venv
    }
    
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    & ".\venv\Scripts\Activate.ps1"
    
    Write-Host "Installing dependencies..." -ForegroundColor Yellow
    pip install --upgrade pip
    pip install -r requirements.txt
    
    Write-Host "✅ Virtual environment ready" -ForegroundColor Green
} else {
    Write-Host "⏭️  Skipping virtual environment setup" -ForegroundColor Yellow
}

# Step 2: Setup Environment File
Write-Host "`n🔧 Checking environment configuration..." -ForegroundColor Cyan

if (-not (Test-Path ".env")) {
    Write-Host "Creating .env file from template..." -ForegroundColor Yellow
    Copy-Item ".env.example" ".env"
    Write-Host "⚠️  Please edit .env file with your configuration" -ForegroundColor Yellow
} else {
    Write-Host "✅ .env file exists" -ForegroundColor Green
}

# Step 3: Start Docker Services
if (-not $SkipDocker) {
    Write-Host "`n🐳 Starting Docker services..." -ForegroundColor Cyan
    
    # Check if Docker is running
    try {
        docker version | Out-Null
        Write-Host "✅ Docker is running" -ForegroundColor Green
    } catch {
        Write-Host "❌ Docker is not running. Please start Docker Desktop" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Starting PostgreSQL and Redis..." -ForegroundColor Yellow
    docker compose up -d db redis
    
    # Wait for services to be healthy
    Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
    $timeout = 60
    $elapsed = 0
    
    do {
        Start-Sleep -Seconds 2
        $elapsed += 2
        $dbHealth = docker compose ps db --format json | ConvertFrom-Json | Select-Object -ExpandProperty Health
        $redisHealth = docker compose ps redis --format json | ConvertFrom-Json | Select-Object -ExpandProperty Health
        
        if ($dbHealth -eq "healthy" -and $redisHealth -eq "healthy") {
            Write-Host "✅ Database and Redis are ready" -ForegroundColor Green
            break
        }
        
        if ($elapsed -ge $timeout) {
            Write-Host "❌ Timeout waiting for services to be ready" -ForegroundColor Red
            Write-Host "Check logs: docker compose logs db redis" -ForegroundColor Yellow
            exit 1
        }
        
        Write-Host "." -NoNewline -ForegroundColor Yellow
    } while ($true)
    
} else {
    Write-Host "⏭️  Skipping Docker services" -ForegroundColor Yellow
}

# Step 4: Database Migrations
if (-not $SkipMigrations) {
    Write-Host "`n🗄️  Setting up database..." -ForegroundColor Cyan
    
    # Activate virtual environment for Flask commands
    & ".\venv\Scripts\Activate.ps1"
    
    $env:FLASK_APP = "run.py"
    
    # Check if migrations directory exists
    if (-not (Test-Path "migrations")) {
        Write-Host "Initializing database migrations..." -ForegroundColor Yellow
        flask db init
    }
    
    # Create migration if needed
    Write-Host "Creating migration..." -ForegroundColor Yellow
    flask db migrate -m "Initial migration"
    
    # Apply migrations
    Write-Host "Applying migrations..." -ForegroundColor Yellow
    flask db upgrade
    
    Write-Host "✅ Database setup complete" -ForegroundColor Green
} else {
    Write-Host "⏭️  Skipping database migrations" -ForegroundColor Yellow
}

# Step 5: Start Application
Write-Host "`n🎯 Starting AI Secretary application..." -ForegroundColor Cyan

# Activate virtual environment
& ".\venv\Scripts\Activate.ps1"

Write-Host "Application will be available at: http://localhost:5000" -ForegroundColor Green
Write-Host "Health check: http://localhost:5000/api/v1/health" -ForegroundColor Green
Write-Host "`nPress Ctrl+C to stop the application" -ForegroundColor Yellow

# Set environment variables
$env:FLASK_APP = "run.py"
$env:FLASK_ENV = "development"

# Start the application
python run.py