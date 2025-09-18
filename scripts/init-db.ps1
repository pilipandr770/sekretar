# Database initialization script with new initialization system

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

# Try using the new initialization system first
Write-Host "Attempting to use new database initialization system..." -ForegroundColor Yellow
python init_database.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "Database initialization completed using new system!" -ForegroundColor Green
    exit 0
}

Write-Host "New system unavailable, falling back to migration-based initialization..." -ForegroundColor Yellow

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

# Create admin user
Write-Host "Creating admin user..." -ForegroundColor Yellow
python create_admin_user.py

Write-Host "Database initialization completed!" -ForegroundColor Green