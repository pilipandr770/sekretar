# Complete i18n workflow script

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("extract", "update", "compile", "full")]
    [string]$Action,
    
    [string]$Language = ""
)

Write-Host "AI Secretary i18n Workflow" -ForegroundColor Green
Write-Host "=========================" -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:FLASK_APP = "run.py"

switch ($Action) {
    "extract" {
        Write-Host "Step 1: Extracting messages..." -ForegroundColor Yellow
        & ".\scripts\extract-messages.ps1"
    }
    
    "update" {
        Write-Host "Step 2: Updating translations..." -ForegroundColor Yellow
        if ($Language) {
            & ".\scripts\update-translations.ps1" -Language $Language
        } else {
            & ".\scripts\update-translations.ps1"
        }
    }
    
    "compile" {
        Write-Host "Step 3: Compiling translations..." -ForegroundColor Yellow
        if ($Language) {
            & ".\scripts\compile-translations.ps1" -Language $Language
        } else {
            & ".\scripts\compile-translations.ps1"
        }
    }
    
    "full" {
        Write-Host "Running full i18n workflow..." -ForegroundColor Cyan
        
        Write-Host "`nStep 1: Extracting messages..." -ForegroundColor Yellow
        & ".\scripts\extract-messages.ps1"
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Message extraction failed!" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "`nStep 2: Updating translations..." -ForegroundColor Yellow
        if ($Language) {
            & ".\scripts\update-translations.ps1" -Language $Language
        } else {
            & ".\scripts\update-translations.ps1"
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Translation update failed!" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "`nStep 3: Compiling translations..." -ForegroundColor Yellow
        if ($Language) {
            & ".\scripts\compile-translations.ps1" -Language $Language
        } else {
            & ".\scripts\compile-translations.ps1"
        }
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "Translation compilation failed!" -ForegroundColor Red
            exit 1
        }
        
        Write-Host "`nFull workflow completed successfully!" -ForegroundColor Green
        Write-Host "Restart the application to load new translations." -ForegroundColor White
    }
}

Write-Host "`ni18n workflow completed!" -ForegroundColor Green

# Show summary
Write-Host "`nTranslation Status:" -ForegroundColor Cyan
$languages = @("en", "de", "uk")

foreach ($lang in $languages) {
    $poFile = "app\translations\$lang\LC_MESSAGES\messages.po"
    $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
    
    if (Test-Path $poFile) {
        $poStatus = "✓"
        $poColor = "Green"
    } else {
        $poStatus = "✗"
        $poColor = "Red"
    }
    
    if (Test-Path $moFile) {
        $moStatus = "✓"
        $moColor = "Green"
    } else {
        $moStatus = "✗"
        $moColor = "Red"
    }
    
    Write-Host "  $lang`: " -NoNewline
    Write-Host "$poStatus .po " -ForegroundColor $poColor -NoNewline
    Write-Host "$moStatus .mo" -ForegroundColor $moColor
}

Write-Host "`nNext steps:" -ForegroundColor Cyan
Write-Host "1. Edit .po files in app/translations/*/LC_MESSAGES/" -ForegroundColor White
Write-Host "2. Run 'scripts\i18n-workflow.ps1 compile' to compile changes" -ForegroundColor White
Write-Host "3. Restart the application to load new translations" -ForegroundColor White