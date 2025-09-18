# Enhanced Database Management Script with New Initialization System

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("init", "health", "repair", "status", "reset", "seed", "migrate")]
    [string]$Action,
    
    [switch]$Force,
    [string]$Environment = "development"
)

Write-Host "🗄️  AI Secretary Database Manager" -ForegroundColor Cyan
Write-Host "=" * 50 -ForegroundColor Cyan

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:FLASK_APP = "run.py"
$env:FLASK_ENV = $Environment

switch ($Action) {
    "init" {
        Write-Host "🔄 Initializing database..." -ForegroundColor Yellow
        
        if ($Force) {
            Write-Host "⚠️  Force mode enabled - existing data will be dropped!" -ForegroundColor Red
            python scripts/database_manager.py init --force
        } else {
            python scripts/database_manager.py init
        }
    }
    
    "health" {
        Write-Host "🔍 Checking database health..." -ForegroundColor Yellow
        python scripts/database_manager.py health
    }
    
    "repair" {
        Write-Host "🔧 Attempting database repair..." -ForegroundColor Yellow
        python scripts/database_manager.py repair
    }
    
    "status" {
        Write-Host "📊 Getting database status..." -ForegroundColor Yellow
        python scripts/database_manager.py status
    }
    
    "reset" {
        Write-Host "⚠️  Resetting database..." -ForegroundColor Red
        
        if ($Force) {
            python scripts/database_manager.py reset --force
        } else {
            Write-Host "This will completely reset the database!" -ForegroundColor Red
            $confirmation = Read-Host "Type 'yes' to confirm"
            
            if ($confirmation -eq "yes") {
                python scripts/database_manager.py reset --force
            } else {
                Write-Host "Reset cancelled." -ForegroundColor Yellow
            }
        }
    }
    
    "seed" {
        Write-Host "🌱 Seeding database with initial data..." -ForegroundColor Yellow
        python create_admin_user.py
    }
    
    "migrate" {
        Write-Host "🔄 Running database migrations..." -ForegroundColor Yellow
        
        # Check if migrations directory exists
        if (-not (Test-Path "migrations\versions")) {
            Write-Host "Initializing migration repository..." -ForegroundColor Yellow
            flask db init
        }
        
        # Create migration if needed
        Write-Host "Creating migration..." -ForegroundColor Yellow
        flask db migrate -m "Auto migration $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
        
        # Apply migrations
        Write-Host "Applying migrations..." -ForegroundColor Yellow
        flask db upgrade
    }
}

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Operation completed successfully!" -ForegroundColor Green
} else {
    Write-Host "❌ Operation failed!" -ForegroundColor Red
    exit 1
}