# Development server startup script

Write-Host "Starting AI Secretary development server..." -ForegroundColor Green

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

# Set environment variables
$env:FLASK_APP = "run.py"
$env:FLASK_ENV = "development"

# Start the development server
Write-Host "Starting Flask development server..." -ForegroundColor Yellow
python run.py