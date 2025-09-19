# Compile translation files

param(
    [string]$Language = ""
)

Write-Host "Compiling translation files..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path ".venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
} elseif (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Using current Python environment." -ForegroundColor Yellow
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

$success = $true

foreach ($lang in $languages) {
    Write-Host "Compiling $lang translations..." -ForegroundColor Yellow
    
    $poFile = "app\translations\$lang\LC_MESSAGES\messages.po"
    
    if (Test-Path $poFile) {
        pybabel compile -d app\translations -l $lang
        if ($LASTEXITCODE -eq 0) {
            Write-Host "Compiled $lang translations" -ForegroundColor Green
            
            # Verify .mo file was created
            $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
            if (Test-Path $moFile) {
                Write-Host "Binary file created: $moFile" -ForegroundColor Gray
            }
        } else {
            Write-Host "Failed to compile $lang translations" -ForegroundColor Red
            $success = $false
        }
    } else {
        Write-Host "Translation file not found: $poFile" -ForegroundColor Yellow
        Write-Host "Run update-translations.ps1 first" -ForegroundColor White
    }
}

if ($success) {
    Write-Host "All translations compiled successfully!" -ForegroundColor Green
    Write-Host "Restart the application to load new translations" -ForegroundColor White
} else {
    Write-Host "Some translations failed to compile" -ForegroundColor Red
    exit 1
}