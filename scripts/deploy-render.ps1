# Render.com deployment preparation script

Write-Host "Preparing for Render.com deployment..." -ForegroundColor Green

# Check if all required files exist
$requiredFiles = @(
    "requirements.txt",
    "render.yaml",
    "run.py",
    "config.py",
    ".env.example"
)

foreach ($file in $requiredFiles) {
    if (-not (Test-Path $file)) {
        Write-Host "Missing required file: $file" -ForegroundColor Red
        exit 1
    }
}

Write-Host "All required files present ✓" -ForegroundColor Green

# Validate requirements.txt
Write-Host "Validating requirements.txt..." -ForegroundColor Yellow
if (-not (Get-Content requirements.txt | Select-String "gunicorn")) {
    Write-Host "Warning: gunicorn not found in requirements.txt" -ForegroundColor Yellow
}

# Check environment variables template
Write-Host "Checking environment variables template..." -ForegroundColor Yellow
$envContent = Get-Content .env.example
$requiredEnvVars = @(
    "DATABASE_URL",
    "REDIS_URL",
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "OPENAI_API_KEY",
    "STRIPE_SECRET_KEY",
    "DB_SCHEMA"
)

foreach ($envVar in $requiredEnvVars) {
    if (-not ($envContent | Select-String $envVar)) {
        Write-Host "Warning: $envVar not found in .env.example" -ForegroundColor Yellow
    }
}

Write-Host "Environment variables template validated ✓" -ForegroundColor Green

# Display deployment checklist
Write-Host "`nRender.com Deployment Checklist:" -ForegroundColor Cyan
Write-Host "1. Create PostgreSQL database on Render" -ForegroundColor White
Write-Host "2. Create Redis instance on Render" -ForegroundColor White
Write-Host "3. Create Web Service from this repository" -ForegroundColor White
Write-Host "4. Create Worker Service for Celery" -ForegroundColor White
Write-Host "5. Set environment variables:" -ForegroundColor White

Write-Host "   Required Environment Variables:" -ForegroundColor Yellow
Write-Host "   - DATABASE_URL (auto-provided by Render)" -ForegroundColor Gray
Write-Host "   - REDIS_URL (auto-provided by Render)" -ForegroundColor Gray
Write-Host "   - SECRET_KEY (generate random string)" -ForegroundColor Gray
Write-Host "   - JWT_SECRET_KEY (generate random string)" -ForegroundColor Gray
Write-Host "   - OPENAI_API_KEY (from OpenAI)" -ForegroundColor Gray
Write-Host "   - STRIPE_SECRET_KEY (from Stripe)" -ForegroundColor Gray
Write-Host "   - STRIPE_PUBLISHABLE_KEY (from Stripe)" -ForegroundColor Gray
Write-Host "   - STRIPE_WEBHOOK_SECRET (from Stripe)" -ForegroundColor Gray
Write-Host "   - DB_SCHEMA=ai_secretary" -ForegroundColor Gray
Write-Host "   - FLASK_ENV=production" -ForegroundColor Gray

Write-Host "`nOptional Environment Variables:" -ForegroundColor Yellow
Write-Host "   - GOOGLE_CLIENT_ID (for calendar integration)" -ForegroundColor Gray
Write-Host "   - GOOGLE_CLIENT_SECRET (for calendar integration)" -ForegroundColor Gray
Write-Host "   - TELEGRAM_BOT_TOKEN (for Telegram bot)" -ForegroundColor Gray
Write-Host "   - SMTP_USERNAME (for email notifications)" -ForegroundColor Gray
Write-Host "   - SMTP_PASSWORD (for email notifications)" -ForegroundColor Gray

Write-Host "`nBuild Commands:" -ForegroundColor Cyan
Write-Host "Web Service Build Command:" -ForegroundColor White
Write-Host "pip install --upgrade pip && pip install -r requirements.txt" -ForegroundColor Gray

Write-Host "`nStart Commands:" -ForegroundColor White
Write-Host "Web Service:" -ForegroundColor White
Write-Host "python -c `"from app import create_app; from app.utils.schema import init_database_schema; app = create_app('production'); init_database_schema(app)`" && flask db upgrade && gunicorn --bind 0.0.0.0:`$PORT --workers 2 --timeout 120 run:app" -ForegroundColor Gray

Write-Host "`nWorker Service:" -ForegroundColor White
Write-Host "celery -A celery_app.celery worker --loglevel=info --concurrency=2" -ForegroundColor Gray

Write-Host "`nDatabase Schema Setup:" -ForegroundColor Cyan
Write-Host "The application will automatically create the 'ai_secretary' schema" -ForegroundColor White
Write-Host "in your PostgreSQL database on first deployment." -ForegroundColor White

Write-Host "`nDeployment ready! 🚀" -ForegroundColor Green
Write-Host "Push your code to GitHub and connect it to Render.com" -ForegroundColor White