# Database initialization script

Write-Host "Initializing database..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:FLASK_APP = "run.py"

# Initialize migration repository if it doesn't exist
if (-not (Test-Path "migrations\versions")) {
    Write-Host "Initializing migration repository..." -ForegroundColor Yellow
    flask db init
}

# Create initial migration
Write-Host "Creating initial migration..." -ForegroundColor Yellow
flask db migrate -m "Initial migration"

# Apply migrations
Write-Host "Applying migrations..." -ForegroundColor Yellow
flask db upgrade

Write-Host "Database initialization completed!" -ForegroundColor Green