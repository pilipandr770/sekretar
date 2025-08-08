# Simple translation status check

Write-Host "AI Secretary Translation Status" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green

$languages = @("en", "de", "uk")

Write-Host "`nChecking translation files..." -ForegroundColor Cyan

foreach ($lang in $languages) {
    Write-Host "`n$lang language:" -ForegroundColor Yellow
    
    $poFile = "app\translations\$lang\LC_MESSAGES\messages.po"
    $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
    
    if (Test-Path $poFile) {
        Write-Host "  ✓ .po file exists" -ForegroundColor Green
    } else {
        Write-Host "  ✗ .po file missing" -ForegroundColor Red
    }
    
    if (Test-Path $moFile) {
        Write-Host "  ✓ .mo file exists" -ForegroundColor Green
    } else {
        Write-Host "  ✗ .mo file missing" -ForegroundColor Red
    }
}

Write-Host "`nTesting translations..." -ForegroundColor Cyan
python scripts/test_translations.py

Write-Host "`nDone!" -ForegroundColor Green