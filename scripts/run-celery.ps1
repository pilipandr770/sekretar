# Celery worker startup script

Write-Host "Starting Celery worker..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Check if .env exists
if (-not (Test-Path ".env")) {
    Write-Host ".env file not found. Please create it from .env.example" -ForegroundColor Red
    exit 1
}

# Start Celery worker
Write-Host "Starting Celery worker..." -ForegroundColor Yellow
celery -A celery_app.celery worker --loglevel=info --pool=solo