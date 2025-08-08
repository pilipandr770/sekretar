# Test runner script

Write-Host "Running tests..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set test environment
$env:FLASK_ENV = "testing"

# Run tests with coverage
Write-Host "Running pytest with coverage..." -ForegroundColor Yellow
pytest --cov=app --cov-report=html --cov-report=term-missing tests/

Write-Host "Tests completed! Check htmlcov/index.html for coverage report." -ForegroundColor Green