# Cross-Browser Testing Script for AI Secretary
# Tests frontend functionality across Chrome, Firefox, Safari, and Edge

param(
    [string]$TestType = "all",
    [string]$OutputDir = "test-results",
    [switch]$Headless,
    [switch]$GenerateReport,
    [string]$BaseUrl = "http://localhost:5000"
)

Write-Host "🌐 AI Secretary Cross-Browser Testing" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan

# Create output directory
if (!(Test-Path $OutputDir)) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
    Write-Host "📁 Created output directory: $OutputDir" -ForegroundColor Green
}

# Browser configurations
$browsers = @{
    "Chrome" = @{
        "executable" = "chrome.exe"
        "args" = @("--no-sandbox", "--disable-web-security", "--disable-features=VizDisplayCompositor")
        "userAgent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    "Firefox" = @{
        "executable" = "firefox.exe"
        "args" = @("-new-instance", "-no-remote")
        "userAgent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0"
    }
    "Edge" = @{
        "executable" = "msedge.exe"
        "args" = @("--no-sandbox", "--disable-web-security")
        "userAgent" = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59"
    }
}

# Test URLs
$testUrls = @{
    "compatibility" = "$BaseUrl/tests/test_cross_browser_compatibility.html?autorun=true"
    "functionality" = "$BaseUrl/tests/frontend_test_runner.html?autorun=true"
    "websocket" = "$BaseUrl/tests/test_websocket_connection.html?autorun=true"
}

function Test-BrowserAvailability {
    param([string]$BrowserName, [hashtable]$BrowserConfig)
    
    $executable = $BrowserConfig.executable
    
    # Check if browser is installed
    $browserPath = Get-Command $executable -ErrorAction SilentlyContinue
    if (-not $browserPath) {
        # Try common installation paths
        $commonPaths = @(
            "${env:ProgramFiles}\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
            "${env:ProgramFiles}\Mozilla Firefox\firefox.exe",
            "${env:ProgramFiles(x86)}\Mozilla Firefox\firefox.exe",
            "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe",
            "${env:ProgramFiles}\Microsoft\Edge\Application\msedge.exe"
        )
        
        foreach ($path in $commonPaths) {
            if (Test-Path $path) {
                if ($path -match "chrome" -and $BrowserName -eq "Chrome") {
                    return $path
                }
                if ($path -match "firefox" -and $BrowserName -eq "Firefox") {
                    return $path
                }
                if ($path -match "msedge" -and $BrowserName -eq "Edge") {
                    return $path
                }
            }
        }
        
        return $null
    }
    
    return $browserPath.Source
}

function Start-BrowserTest {
    param(
        [string]$BrowserName,
        [string]$BrowserPath,
        [hashtable]$BrowserConfig,
        [string]$TestUrl,
        [string]$TestName
    )
    
    Write-Host "🧪 Testing $TestName in $BrowserName..." -ForegroundColor Yellow
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    
    # Prepare browser arguments
    $browserArgs = $BrowserConfig.args + @(
        "--user-data-dir=$(Join-Path $env:TEMP "browser-test-$BrowserName-$timestamp")",
        "--disable-extensions",
        "--disable-plugins",
        "--disable-popup-blocking",
        "--allow-running-insecure-content"
    )
    
    if ($Headless) {
        $browserArgs += "--headless"
    }
    
    # Add test URL
    $browserArgs += $TestUrl
    
    try {
        # Start browser process
        $process = Start-Process -FilePath $BrowserPath -ArgumentList $browserArgs -PassThru -WindowStyle Minimized
        
        if (-not $process) {
            throw "Failed to start $BrowserName process"
        }
        
        Write-Host "   ⏱️ Browser started (PID: $($process.Id)), waiting for test completion..." -ForegroundColor Gray
        
        # Wait for test completion (adjust timeout as needed)
        $timeout = 60 # seconds
        $elapsed = 0
        
        while (-not $process.HasExited -and $elapsed -lt $timeout) {
            Start-Sleep -Seconds 2
            $elapsed += 2
            
            # Show progress
            if ($elapsed % 10 -eq 0) {
                Write-Host "   ⏳ Still running... ($elapsed/$timeout seconds)" -ForegroundColor Gray
            }
        }
        
        # Check if test completed successfully
        if ($process.HasExited) {
            $exitCode = $process.ExitCode
            if ($exitCode -eq 0) {
                Write-Host "   ✅ $BrowserName test completed successfully" -ForegroundColor Green
                return @{ Success = $true; ExitCode = $exitCode; Browser = $BrowserName; Test = $TestName }
            } else {
                Write-Host "   ❌ $BrowserName test failed with exit code: $exitCode" -ForegroundColor Red
                return @{ Success = $false; ExitCode = $exitCode; Browser = $BrowserName; Test = $TestName; Error = "Non-zero exit code" }
            }
        } else {
            # Timeout reached, kill process
            Write-Host "   ⏰ $BrowserName test timed out, terminating..." -ForegroundColor Yellow
            $process.Kill()
            $process.WaitForExit(5000)
            
            return @{ Success = $false; Browser = $BrowserName; Test = $TestName; Error = "Timeout after $timeout seconds" }
        }
        
    } catch {
        Write-Host "   ❌ Error testing $BrowserName`: $($_.Exception.Message)" -ForegroundColor Red
        return @{ Success = $false; Browser = $BrowserName; Test = $TestName; Error = $_.Exception.Message }
    }
}

function Test-ServerAvailability {
    param([string]$Url)
    
    try {
        $response = Invoke-WebRequest -Uri $Url -Method Head -TimeoutSec 10 -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function New-TestReport {
    param([array]$TestResults)
    
    Write-Host "📊 Generating test report..." -ForegroundColor Cyan
    
    $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
    $reportFile = Join-Path $OutputDir "cross_browser_test_report_$timestamp.html"
    
    $html = @"
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cross-Browser Test Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 30px; }
        .summary-card { background: #f8f9fa; padding: 15px; border-radius: 5px; text-align: center; }
        .summary-card.success { background: #d4edda; color: #155724; }
        .summary-card.failure { background: #f8d7da; color: #721c24; }
        .test-results { margin-top: 20px; }
        .browser-section { margin-bottom: 30px; border: 1px solid #ddd; border-radius: 5px; overflow: hidden; }
        .browser-header { background: #007bff; color: white; padding: 15px; font-weight: bold; }
        .test-item { padding: 15px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }
        .test-item:last-child { border-bottom: none; }
        .status-badge { padding: 4px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; }
        .status-success { background: #d4edda; color: #155724; }
        .status-failure { background: #f8d7da; color: #721c24; }
        .error-details { background: #fff3cd; color: #856404; padding: 10px; margin-top: 10px; border-radius: 3px; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🌐 Cross-Browser Test Report</h1>
            <p>Generated on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")</p>
        </div>
        
        <div class="summary">
"@

    # Calculate summary statistics
    $totalTests = $TestResults.Count
    $successfulTests = ($TestResults | Where-Object { $_.Success }).Count
    $failedTests = $totalTests - $successfulTests
    $successRate = if ($totalTests -gt 0) { [math]::Round(($successfulTests / $totalTests) * 100, 2) } else { 0 }
    
    $html += @"
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div style="font-size: 24px; font-weight: bold;">$totalTests</div>
            </div>
            <div class="summary-card success">
                <h3>Successful</h3>
                <div style="font-size: 24px; font-weight: bold;">$successfulTests</div>
            </div>
            <div class="summary-card failure">
                <h3>Failed</h3>
                <div style="font-size: 24px; font-weight: bold;">$failedTests</div>
            </div>
            <div class="summary-card">
                <h3>Success Rate</h3>
                <div style="font-size: 24px; font-weight: bold;">$successRate%</div>
            </div>
        </div>
        
        <div class="test-results">
"@

    # Group results by browser
    $browserGroups = $TestResults | Group-Object -Property Browser
    
    foreach ($browserGroup in $browserGroups) {
        $browserName = $browserGroup.Name
        $browserTests = $browserGroup.Group
        
        $html += @"
            <div class="browser-section">
                <div class="browser-header">$browserName</div>
"@
        
        foreach ($test in $browserTests) {
            $statusClass = if ($test.Success) { "status-success" } else { "status-failure" }
            $statusText = if ($test.Success) { "✅ Passed" } else { "❌ Failed" }
            
            $html += @"
                <div class="test-item">
                    <div>
                        <strong>$($test.Test)</strong>
                    </div>
                    <div class="status-badge $statusClass">$statusText</div>
                </div>
"@
            
            if (-not $test.Success -and $test.Error) {
                $html += @"
                <div class="error-details">
                    <strong>Error:</strong> $($test.Error)
                </div>
"@
            }
        }
        
        $html += "</div>"
    }
    
    $html += @"
        </div>
    </div>
</body>
</html>
"@

    $html | Out-File -FilePath $reportFile -Encoding UTF8
    Write-Host "📄 Test report generated: $reportFile" -ForegroundColor Green
    
    return $reportFile
}

# Main execution
Write-Host "🔍 Checking server availability..." -ForegroundColor Yellow

if (-not (Test-ServerAvailability $BaseUrl)) {
    Write-Host "❌ Server not available at $BaseUrl" -ForegroundColor Red
    Write-Host "   Please start the AI Secretary application first" -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Server is available" -ForegroundColor Green

# Check browser availability
$availableBrowsers = @{}
foreach ($browserName in $browsers.Keys) {
    $browserPath = Test-BrowserAvailability $browserName $browsers[$browserName]
    if ($browserPath) {
        $availableBrowsers[$browserName] = $browserPath
        Write-Host "✅ $browserName found at: $browserPath" -ForegroundColor Green
    } else {
        Write-Host "❌ $browserName not found" -ForegroundColor Red
    }
}

if ($availableBrowsers.Count -eq 0) {
    Write-Host "❌ No browsers available for testing" -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Starting cross-browser tests..." -ForegroundColor Cyan

# Determine which tests to run
$testsToRun = switch ($TestType) {
    "compatibility" { @("compatibility") }
    "functionality" { @("functionality") }
    "websocket" { @("websocket") }
    "all" { @("compatibility", "functionality", "websocket") }
    default { @("compatibility", "functionality") }
}

$allResults = @()

# Run tests for each browser and test type
foreach ($browserName in $availableBrowsers.Keys) {
    $browserPath = $availableBrowsers[$browserName]
    $browserConfig = $browsers[$browserName]
    
    Write-Host "`n🌐 Testing $browserName" -ForegroundColor Magenta
    Write-Host "========================" -ForegroundColor Magenta
    
    foreach ($testType in $testsToRun) {
        if ($testUrls.ContainsKey($testType)) {
            $testUrl = $testUrls[$testType]
            $result = Start-BrowserTest $browserName $browserPath $browserConfig $testUrl $testType
            $allResults += $result
        }
    }
}

# Generate summary
Write-Host "`n📊 Test Summary" -ForegroundColor Cyan
Write-Host "===============" -ForegroundColor Cyan

$successfulTests = ($allResults | Where-Object { $_.Success }).Count
$failedTests = ($allResults | Where-Object { -not $_.Success }).Count
$totalTests = $allResults.Count

Write-Host "Total Tests: $totalTests" -ForegroundColor White
Write-Host "Successful: $successfulTests" -ForegroundColor Green
Write-Host "Failed: $failedTests" -ForegroundColor Red

if ($failedTests -gt 0) {
    Write-Host "`n❌ Failed Tests:" -ForegroundColor Red
    $allResults | Where-Object { -not $_.Success } | ForEach-Object {
        Write-Host "   • $($_.Browser) - $($_.Test): $($_.Error)" -ForegroundColor Red
    }
}

# Generate HTML report if requested
if ($GenerateReport) {
    $reportFile = New-TestReport $allResults
    
    # Try to open report in default browser
    try {
        Start-Process $reportFile
        Write-Host "📖 Report opened in default browser" -ForegroundColor Green
    } catch {
        Write-Host "📖 Report saved to: $reportFile" -ForegroundColor Green
    }
}

# Exit with appropriate code
if ($failedTests -eq 0) {
    Write-Host "`n🎉 All cross-browser tests passed!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`n⚠️ Some tests failed. Check the report for details." -ForegroundColor Yellow
    exit 1
}