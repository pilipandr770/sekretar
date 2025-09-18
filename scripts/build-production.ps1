# Production build script with translation compilation

param(
    [string]$Tag = "latest",
    [switch]$NoBuild = $false,
    [switch]$Push = $false,
    [string]$Registry = ""
)

Write-Host "AI Secretary Production Build" -ForegroundColor Green
Write-Host "============================" -ForegroundColor Green

# Set image name
$imageName = "ai-secretary"
if ($Registry) {
    $imageName = "$Registry/$imageName"
}

# Pre-build translation compilation
Write-Host "`nStep 1: Pre-compiling translations..." -ForegroundColor Yellow

# Activate virtual environment if available
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
    Write-Host "Virtual environment activated" -ForegroundColor Gray
}

# Run full i18n workflow
Write-Host "Running i18n workflow..." -ForegroundColor Gray
& ".\scripts\i18n-workflow.ps1" -Action "full"

if ($LASTEXITCODE -ne 0) {
    Write-Host "Translation compilation failed!" -ForegroundColor Red
    exit 1
}

# Verify translation files
$languages = @("en", "de", "uk")
$translationReady = $true

foreach ($lang in $languages) {
    $moFile = "app\translations\$lang\LC_MESSAGES\messages.mo"
    if (!(Test-Path $moFile)) {
        Write-Host "Missing compiled translation: $moFile" -ForegroundColor Red
        $translationReady = $false
    } else {
        $size = (Get-Item $moFile).Length
        Write-Host "✓ $lang translation ready ($size bytes)" -ForegroundColor Green
    }
}

if (!$translationReady) {
    Write-Host "Translation files are not ready for production build!" -ForegroundColor Red
    exit 1
}

if (!$NoBuild) {
    # Build Docker image
    Write-Host "`nStep 2: Building Docker image..." -ForegroundColor Yellow
    Write-Host "Image: $imageName`:$Tag" -ForegroundColor Gray
    
    docker build -f Dockerfile.prod -t "$imageName`:$Tag" .
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Docker build failed!" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "Docker image built successfully!" -ForegroundColor Green
    
    # Show image info
    Write-Host "`nImage Information:" -ForegroundColor Cyan
    docker images "$imageName`:$Tag" --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}\t{{.CreatedAt}}"
}

if ($Push -and !$NoBuild) {
    Write-Host "`nStep 3: Pushing to registry..." -ForegroundColor Yellow
    
    if (!$Registry) {
        Write-Host "Registry not specified. Use -Registry parameter." -ForegroundColor Red
        exit 1
    }
    
    docker push "$imageName`:$Tag"
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "Image pushed successfully!" -ForegroundColor Green
    } else {
        Write-Host "Failed to push image!" -ForegroundColor Red
        exit 1
    }
}

Write-Host "`nProduction build completed!" -ForegroundColor Green
Write-Host "Image: $imageName`:$Tag" -ForegroundColor White

# Show next steps
Write-Host "`nNext Steps:" -ForegroundColor Cyan
Write-Host "1. Test the image: docker run -p 5000:5000 $imageName`:$Tag" -ForegroundColor White
Write-Host "2. Deploy with: docker-compose -f docker-compose.prod.yml up -d" -ForegroundColor White
Write-Host "3. Monitor logs: docker-compose -f docker-compose.prod.yml logs -f app" -ForegroundColor White