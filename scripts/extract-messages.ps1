# Extract translatable messages from source code

Write-Host "Extracting translatable messages..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:FLASK_APP = "run.py"

# Extract messages
Write-Host "Extracting messages to messages.pot..." -ForegroundColor Yellow
pybabel extract -F babel.cfg -k _l -o messages.pot .

if ($LASTEXITCODE -eq 0) {
    Write-Host "Messages extracted successfully!" -ForegroundColor Green
    Write-Host "File created: messages.pot" -ForegroundColor White
} else {
    Write-Host "Failed to extract messages" -ForegroundColor Red
    exit 1
}

Write-Host "Next steps:" -ForegroundColor Cyan
Write-Host "1. Run update-translations.ps1 to update existing translations" -ForegroundColor White
Write-Host "2. Edit .po files in app/translations/*/LC_MESSAGES/" -ForegroundColor White
Write-Host "3. Run compile-translations.ps1 to compile translations" -ForegroundColor White