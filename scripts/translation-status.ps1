# Check translation status

Write-Host "AI Secretary Translation Status" -ForegroundColor Green
Write-Host "===============================" -ForegroundColor Green

# Check if files exist
$languages = @("en", "de", "uk")
$allGood = $true

foreach ($lang in $languages) {
    $poFile = "app\translations\$lang\LC_MESSAGES\messages.po"
    $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
    
    $langName = switch ($lang) {
        'en' { 'English' }
        'de' { 'Deutsch' }
        'uk' { 'Українська' }
    }
    
    Write-Host "`n$lang ($langName):" -ForegroundColor Cyan
    
    if (Test-Path $poFile) {
        Write-Host "  ✓ .po file exists" -ForegroundColor Green
    } else {
        Write-Host "  ✗ .po file missing" -ForegroundColor Red
        $allGood = $false
    }
    
    if (Test-Path $moFile) {
        Write-Host "  ✓ .mo file exists" -ForegroundColor Green
        
        # Check file size
        $size = (Get-Item $moFile).Length
        Write-Host "  📊 File size: $size bytes" -ForegroundColor Gray
    } else {
        Write-Host "  ✗ .mo file missing" -ForegroundColor Red
        $allGood = $false
    }
}

Write-Host "`nOverall Status:" -ForegroundColor Cyan
if ($allGood) {
    Write-Host "✅ All translation files are ready!" -ForegroundColor Green
} else {
    Write-Host "❌ Some translation files are missing" -ForegroundColor Red
    Write-Host "Run: scripts\i18n-workflow.ps1 full" -ForegroundColor Yellow
}

# Test translations programmatically
Write-Host "`nRunning translation tests..." -ForegroundColor Cyan
python scripts/test_translations.py

Write-Host "`nQuick Commands:" -ForegroundColor Cyan
Write-Host "  Full workflow:    scripts\i18n-workflow.ps1 full" -ForegroundColor White
Write-Host "  Extract messages: scripts\i18n-workflow.ps1 extract" -ForegroundColor White
Write-Host "  Update .po files: scripts\i18n-workflow.ps1 update" -ForegroundColor White
Write-Host "  Compile .mo files: scripts\i18n-workflow.ps1 compile" -ForegroundColor White
Write-Host "  Test translations: python scripts\test_translations.py" -ForegroundColor White