# Update existing translation files

param(
    [string]$Language = ""
)

Write-Host "Updating translation files..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:FLASK_APP = "run.py"

# Check if messages.pot exists
if (-not (Test-Path "messages.pot")) {
    Write-Host "messages.pot not found. Run extract-messages.ps1 first." -ForegroundColor Red
    exit 1
}

$languages = @("en", "de", "uk")

if ($Language) {
    if ($Language -in $languages) {
        $languages = @($Language)
    } else {
        Write-Host "Invalid language: $Language. Available: en, de, uk" -ForegroundColor Red
        exit 1
    }
}

foreach ($lang in $languages) {
    Write-Host "Updating $lang translations..." -ForegroundColor Yellow
    
    $poFile = "app\translations\$lang\LC_MESSAGES\messages.po"
    
    if (Test-Path $poFile) {
        # Update existing translation
        pybabel update -i messages.pot -d app\translations -l $lang
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Updated $lang translations" -ForegroundColor Green
        } else {
            Write-Host "Failed to update $lang translations" -ForegroundColor Red
        }
    } else {
        # Initialize new translation
        Write-Host "Initializing new $lang translation..." -ForegroundColor Cyan
        pybabel init -i messages.pot -d app\translations -l $lang
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Initialized $lang translations" -ForegroundColor Green
        } else {
            Write-Host "Failed to initialize $lang translations" -ForegroundColor Red
        }
    }
}

Write-Host "Translation update completed!" -ForegroundColor Green
Write-Host "Edit the .po files and then run compile-translations.ps1" -ForegroundColor White