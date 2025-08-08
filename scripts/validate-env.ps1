# Validate .env file configuration

Write-Host "Validating .env configuration..." -ForegroundColor Green

# Check if .env file exists
if (-not (Test-Path ".env")) {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    Write-Host "Copy .env.example to .env and configure it" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ .env file found" -ForegroundColor Green

# Load .env file
$envVars = @{}
Get-Content ".env" | ForEach-Object {
    if ($_ -match "^([^#][^=]+)=(.*)$") {
        $envVars[$matches[1]] = $matches[2]
    }
}

Write-Host "`nChecking required variables..." -ForegroundColor Cyan

# Required variables
$required = @(
    "FLASK_APP",
    "SECRET_KEY", 
    "JWT_SECRET_KEY",
    "DATABASE_URL",
    "REDIS_URL"
)

$missing = @()
foreach ($var in $required) {
    if ($envVars.ContainsKey($var) -and $envVars[$var] -ne "") {
        Write-Host "✅ $var" -ForegroundColor Green
    } else {
        Write-Host "❌ $var (missing or empty)" -ForegroundColor Red
        $missing += $var
    }
}

# Check for default/example values
Write-Host "`nChecking for default values that need to be changed..." -ForegroundColor Cyan

$defaultValues = @{
    "SECRET_KEY" = @("your-secret-key-here", "dev-secret-key")
    "JWT_SECRET_KEY" = @("your-jwt-secret-key-here", "jwt-secret-key")
    "OPENAI_API_KEY" = @("your-openai-api-key-here", "sk-your-openai-api-key-here")
    "DATABASE_URL" = @("postgresql://username:password@localhost")
}

$needsUpdate = @()
foreach ($var in $defaultValues.Keys) {
    if ($envVars.ContainsKey($var)) {
        $value = $envVars[$var]
        $isDefault = $false
        
        foreach ($defaultVal in $defaultValues[$var]) {
            if ($value -like "*$defaultVal*") {
                $isDefault = $true
                break
            }
        }
        
        if ($isDefault) {
            Write-Host "⚠️  $var (using default/example value)" -ForegroundColor Yellow
            $needsUpdate += $var
        } else {
            Write-Host "✅ $var (configured)" -ForegroundColor Green
        }
    }
}

# Optional but recommended variables
Write-Host "`nChecking optional variables..." -ForegroundColor Cyan

$optional = @(
    "OPENAI_API_KEY",
    "STRIPE_SECRET_KEY",
    "GOOGLE_CLIENT_ID",
    "TELEGRAM_BOT_TOKEN"
)

foreach ($var in $optional) {
    if ($envVars.ContainsKey($var) -and $envVars[$var] -ne "" -and $envVars[$var] -notlike "*your-*") {
        Write-Host "✅ $var (configured)" -ForegroundColor Green
    } else {
        Write-Host "⚠️  $var (not configured - some features may not work)" -ForegroundColor Yellow
    }
}

# Summary
Write-Host "`n" + "="*50 -ForegroundColor Cyan
Write-Host "VALIDATION SUMMARY" -ForegroundColor Cyan
Write-Host "="*50 -ForegroundColor Cyan

if ($missing.Count -eq 0 -and $needsUpdate.Count -eq 0) {
    Write-Host "🎉 Configuration looks good!" -ForegroundColor Green
    Write-Host "You can start the application with: .\scripts\run-dev.ps1" -ForegroundColor White
} else {
    if ($missing.Count -gt 0) {
        Write-Host "❌ Missing required variables:" -ForegroundColor Red
        $missing | ForEach-Object { Write-Host "   - $_" -ForegroundColor Red }
    }
    
    if ($needsUpdate.Count -gt 0) {
        Write-Host "⚠️  Variables with default values that should be updated:" -ForegroundColor Yellow
        $needsUpdate | ForEach-Object { Write-Host "   - $_" -ForegroundColor Yellow }
    }
    
    Write-Host "`nNext steps:" -ForegroundColor Cyan
    Write-Host "1. Edit .env file with proper values" -ForegroundColor White
    Write-Host "2. See docs/environment-setup.md for detailed instructions" -ForegroundColor White
    Write-Host "3. Run this script again to validate" -ForegroundColor White
}

Write-Host "`nFor detailed setup instructions, see:" -ForegroundColor Cyan
Write-Host "docs/environment-setup.md" -ForegroundColor White