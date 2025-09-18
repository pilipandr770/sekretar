# Translation system health check script

param(
    [string]$Environment = "production",
    [string]$BaseUrl = "",
    [switch]$Detailed = $false,
    [switch]$Json = $false
)

# Configuration
$DEFAULT_URLS = @{
    "production" = "https://api.yourdomain.com"
    "staging" = "https://staging-api.yourdomain.com"
    "development" = "http://localhost:5000"
}

if (!$BaseUrl) {
    $BaseUrl = $DEFAULT_URLS[$Environment]
    if (!$BaseUrl) {
        Write-Host "Unknown environment: $Environment" -ForegroundColor Red
        exit 1
    }
}

$results = @{
    timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss")
    environment = $Environment
    base_url = $BaseUrl
    overall_status = "unknown"
    checks = @{}
    errors = @()
}

function Test-ApiEndpoint {
    param([string]$Url, [string]$Name)
    
    try {
        $response = Invoke-RestMethod -Uri $Url -Method GET -TimeoutSec 10
        return @{
            name = $Name
            status = "pass"
            response_time = 0
            data = $response
        }
    } catch {
        return @{
            name = $Name
            status = "fail"
            error = $_.Exception.Message
            response_time = 0
        }
    }
}

function Test-TranslationEndpoint {
    param([string]$BaseUrl, [string]$Language, [string]$Key)
    
    $url = "$BaseUrl/api/v1/translate?key=$Key`&lang=$Language"
    
    try {
        $start = Get-Date
        $response = Invoke-RestMethod -Uri $url -Method GET -TimeoutSec 10
        $duration = ((Get-Date) - $start).TotalMilliseconds
        
        if ($response -and $response.translation) {
            return @{
                language = $Language
                key = $Key
                status = "pass"
                translation = $response.translation
                response_time = [math]::Round($duration, 2)
            }
        } else {
            return @{
                language = $Language
                key = $Key
                status = "fail"
                error = "No translation returned"
                response_time = [math]::Round($duration, 2)
            }
        }
    } catch {
        return @{
            language = $Language
            key = $Key
            status = "fail"
            error = $_.Exception.Message
            response_time = 0
        }
    }
}

Write-Host "AI Secretary Translation Health Check" -ForegroundColor Green
Write-Host "====================================" -ForegroundColor Green
Write-Host "Environment: $Environment" -ForegroundColor Cyan
Write-Host "Base URL: $BaseUrl" -ForegroundColor Cyan
Write-Host ""

# Test 1: API Health
Write-Host "1. Testing API health..." -ForegroundColor Yellow
$healthCheck = Test-ApiEndpoint -Url "$BaseUrl/api/v1/health" -Name "API Health"
$results.checks.api_health = $healthCheck

if ($healthCheck.status -eq "pass") {
    Write-Host "   ✓ API is healthy" -ForegroundColor Green
} else {
    Write-Host "   ✗ API health check failed: $($healthCheck.error)" -ForegroundColor Red
    $results.errors += "API health check failed"
}

# Test 2: Languages endpoint
Write-Host "2. Testing languages endpoint..." -ForegroundColor Yellow
$languagesCheck = Test-ApiEndpoint -Url "$BaseUrl/api/v1/languages" -Name "Languages"
$results.checks.languages = $languagesCheck

if ($languagesCheck.status -eq "pass") {
    $availableLanguages = $languagesCheck.data.data
    Write-Host "   ✓ Available languages: $($availableLanguages -join ', ')" -ForegroundColor Green
} else {
    Write-Host "   ✗ Languages endpoint failed: $($languagesCheck.error)" -ForegroundColor Red
    $results.errors += "Languages endpoint failed"
}

# Test 3: Translation endpoints
Write-Host "3. Testing translation endpoints..." -ForegroundColor Yellow
$languages = @("en", "de", "uk")
$testKeys = @("Welcome", "Login", "Dashboard", "Settings", "Error")

$translationResults = @()

foreach ($lang in $languages) {
    Write-Host "   Testing $lang translations..." -ForegroundColor Gray
    
    foreach ($key in $testKeys) {
        $translationTest = Test-TranslationEndpoint -BaseUrl $BaseUrl -Language $lang -Key $key
        $translationResults += $translationTest
        
        if ($translationTest.status -eq "pass") {
            if ($Detailed) {
                Write-Host "     ✓ $key -> $($translationTest.translation) ($($translationTest.response_time)ms)" -ForegroundColor Green
            }
        } else {
            Write-Host "     ✗ $key failed: $($translationTest.error)" -ForegroundColor Red
            $results.errors += "$lang translation for '$key' failed"
        }
    }
}

$results.checks.translations = $translationResults

# Test 4: Performance check
Write-Host "4. Testing translation performance..." -ForegroundColor Yellow
$performanceTests = @()

foreach ($lang in $languages) {
    $start = Get-Date
    $batchTest = @()
    
    foreach ($key in $testKeys) {
        $test = Test-TranslationEndpoint -BaseUrl $BaseUrl -Language $lang -Key $key
        $batchTest += $test
    }
    
    $totalTime = ((Get-Date) - $start).TotalMilliseconds
    $avgTime = $totalTime / $testKeys.Count
    
    $performanceTest = @{
        language = $lang
        total_time = [math]::Round($totalTime, 2)
        average_time = [math]::Round($avgTime, 2)
        tests_count = $testKeys.Count
        success_rate = [math]::Round(($batchTest | Where-Object { $_.status -eq "pass" }).Count / $testKeys.Count * 100, 2)
    }
    
    $performanceTests += $performanceTest
    
    if ($avgTime -lt 100) {
        Write-Host "   ✓ $lang average response time: $([math]::Round($avgTime, 2))ms" -ForegroundColor Green
    } elseif ($avgTime -lt 500) {
        Write-Host "   ⚠ $lang average response time: $([math]::Round($avgTime, 2))ms (slow)" -ForegroundColor Yellow
    } else {
        Write-Host "   ✗ $lang average response time: $([math]::Round($avgTime, 2))ms (too slow)" -ForegroundColor Red
        $results.errors += "$lang translations are too slow"
    }
}

$results.checks.performance = $performanceTests

# Test 5: Cache performance (if available)
Write-Host "5. Testing cache performance..." -ForegroundColor Yellow
try {
    $cacheCheck = Test-ApiEndpoint -Url "$BaseUrl/admin/i18n/performance" -Name "Cache Performance"
    
    if ($cacheCheck.status -eq "pass") {
        $cacheStats = $cacheCheck.data
        $hitRate = $cacheStats.cache_stats.hit_rate
        
        if ($hitRate -gt 80) {
            Write-Host "   ✓ Cache hit rate: $hitRate%" -ForegroundColor Green
        } elseif ($hitRate -gt 50) {
            Write-Host "   ⚠ Cache hit rate: $hitRate% (could be better)" -ForegroundColor Yellow
        } else {
            Write-Host "   ✗ Cache hit rate: $hitRate% (poor performance)" -ForegroundColor Red
            $results.errors += "Poor cache performance"
        }
        
        $results.checks.cache = $cacheStats
    } else {
        Write-Host "   ⚠ Cache performance endpoint not available" -ForegroundColor Yellow
    }
} catch {
    Write-Host "   ⚠ Cache performance check skipped" -ForegroundColor Yellow
}

# Determine overall status
$totalErrors = $results.errors.Count
if ($totalErrors -eq 0) {
    $results.overall_status = "healthy"
    $statusColor = "Green"
    $statusIcon = "✅"
} elseif ($totalErrors -le 2) {
    $results.overall_status = "warning"
    $statusColor = "Yellow"
    $statusIcon = "⚠️"
} else {
    $results.overall_status = "critical"
    $statusColor = "Red"
    $statusIcon = "❌"
}

# Output results
Write-Host ""
Write-Host "Health Check Summary" -ForegroundColor Cyan
Write-Host "===================" -ForegroundColor Cyan
Write-Host "$statusIcon Overall Status: $($results.overall_status.ToUpper())" -ForegroundColor $statusColor

if ($totalErrors -gt 0) {
    Write-Host ""
    Write-Host "Issues Found:" -ForegroundColor Red
    foreach ($error in $results.errors) {
        Write-Host "  • $error" -ForegroundColor Red
    }
}

if ($Json) {
    Write-Host ""
    Write-Host "JSON Output:" -ForegroundColor Cyan
    $results | ConvertTo-Json -Depth 10
}

# Exit with appropriate code
if ($results.overall_status -eq "critical") {
    exit 2
} elseif ($results.overall_status -eq "warning") {
    exit 1
} else {
    exit 0
}