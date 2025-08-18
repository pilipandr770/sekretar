#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Start Celery workers for the AI Secretary application.

.DESCRIPTION
    This script starts Celery workers with proper configuration for the AI Secretary SaaS platform.
    It supports different worker types and provides options for development and production environments.

.PARAMETER WorkerType
    Type of worker to start: 'all', 'default', 'billing', 'kyb', 'notifications', 'dead_letter'

.PARAMETER LogLevel
    Celery log level: 'debug', 'info', 'warning', 'error', 'critical'

.PARAMETER Concurrency
    Number of worker processes to start

.PARAMETER Beat
    Start Celery beat scheduler for periodic tasks

.EXAMPLE
    .\run-celery.ps1
    Start default workers with info logging

.EXAMPLE
    .\run-celery.ps1 -WorkerType billing -LogLevel debug
    Start only billing workers with debug logging

.EXAMPLE
    .\run-celery.ps1 -Beat
    Start workers with beat scheduler
#>

param(
    [Parameter()]
    [ValidateSet('all', 'default', 'billing', 'kyb', 'notifications', 'dead_letter')]
    [string]$WorkerType = 'all',
    
    [Parameter()]
    [ValidateSet('debug', 'info', 'warning', 'error', 'critical')]
    [string]$LogLevel = 'info',
    
    [Parameter()]
    [int]$Concurrency = 4,
    
    [Parameter()]
    [switch]$Beat
)

# Set error action preference
$ErrorActionPreference = "Stop"

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

# Change to project root
Push-Location $ProjectRoot

try {
    Write-Host "Starting Celery workers for AI Secretary..." -ForegroundColor Green
    Write-Host "Project root: $ProjectRoot" -ForegroundColor Gray
    Write-Host "Worker type: $WorkerType" -ForegroundColor Gray
    Write-Host "Log level: $LogLevel" -ForegroundColor Gray
    Write-Host "Concurrency: $Concurrency" -ForegroundColor Gray
    
    # Check if virtual environment is activated
    if (-not $env:VIRTUAL_ENV) {
        Write-Warning "Virtual environment not detected. Activating .venv..."
        if (Test-Path ".venv\Scripts\Activate.ps1") {
            & ".venv\Scripts\Activate.ps1"
        } else {
            Write-Error "Virtual environment not found. Please run setup.ps1 first."
        }
    }
    
    # Check if Redis is running
    Write-Host "Checking Redis connection..." -ForegroundColor Yellow
    try {
        $redisTest = python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=1); r.ping(); print('Redis OK')" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✓ Redis is running" -ForegroundColor Green
        } else {
            Write-Warning "Redis may not be running. Workers will retry connection."
        }
    } catch {
        Write-Warning "Could not test Redis connection: $_"
    }
    
    # Build Celery command
    $celeryCmd = @('celery', '-A', 'celery_app', 'worker')
    $celeryCmd += @('--loglevel', $LogLevel)
    $celeryCmd += @('--concurrency', $Concurrency)
    
    # Add queue specification based on worker type
    switch ($WorkerType) {
        'default' {
            $celeryCmd += @('-Q', 'default')
            Write-Host "Starting default queue workers..." -ForegroundColor Cyan
        }
        'billing' {
            $celeryCmd += @('-Q', 'billing')
            Write-Host "Starting billing queue workers..." -ForegroundColor Cyan
        }
        'kyb' {
            $celeryCmd += @('-Q', 'kyb')
            Write-Host "Starting KYB queue workers..." -ForegroundColor Cyan
        }
        'notifications' {
            $celeryCmd += @('-Q', 'notifications')
            Write-Host "Starting notifications queue workers..." -ForegroundColor Cyan
        }
        'dead_letter' {
            $celeryCmd += @('-Q', 'dead_letter')
            Write-Host "Starting dead letter queue workers..." -ForegroundColor Cyan
        }
        'all' {
            $celeryCmd += @('-Q', 'default,billing,kyb,notifications,dead_letter')
            Write-Host "Starting all queue workers..." -ForegroundColor Cyan
        }
    }
    
    # Start beat scheduler if requested
    if ($Beat) {
        Write-Host "Starting Celery beat scheduler..." -ForegroundColor Magenta
        
        # Start beat in background
        $beatCmd = @('celery', '-A', 'celery_app', 'beat', '--loglevel', $LogLevel)
        Start-Process -FilePath 'python' -ArgumentList ('-m', 'celery', '-A', 'celery_app', 'beat', '--loglevel', $LogLevel) -NoNewWindow
        
        Start-Sleep -Seconds 2
        Write-Host "✓ Beat scheduler started" -ForegroundColor Green
    }
    
    # Display worker information
    Write-Host "`nWorker Configuration:" -ForegroundColor Yellow
    Write-Host "  Queues: $(if ($WorkerType -eq 'all') { 'default, billing, kyb, notifications, dead_letter' } else { $WorkerType })" -ForegroundColor Gray
    Write-Host "  Concurrency: $Concurrency processes" -ForegroundColor Gray
    Write-Host "  Log Level: $LogLevel" -ForegroundColor Gray
    Write-Host "  Beat Scheduler: $(if ($Beat) { 'Enabled' } else { 'Disabled' })" -ForegroundColor Gray
    
    Write-Host "`nStarting workers... (Press Ctrl+C to stop)" -ForegroundColor Yellow
    Write-Host "=" * 50 -ForegroundColor Gray
    
    # Start the workers
    & python -m $celeryCmd
    
} catch {
    Write-Error "Failed to start Celery workers: $_"
    exit 1
} finally {
    # Return to original location
    Pop-Location
}