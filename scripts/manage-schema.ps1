# Database schema management script

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("create", "drop", "info")]
    [string]$Action,
    
    [string]$SchemaName = "ai_secretary"
)

Write-Host "Managing database schema..." -ForegroundColor Green

# Activate virtual environment
if (Test-Path "venv\Scripts\Activate.ps1") {
    & ".\venv\Scripts\Activate.ps1"
} else {
    Write-Host "Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Set environment variables
$env:FLASK_APP = "run.py"
$env:DB_SCHEMA = $SchemaName

switch ($Action) {
    "create" {
        Write-Host "Creating schema: $SchemaName" -ForegroundColor Yellow
        python scripts/schema_create.py
    }
    
    "drop" {
        Write-Host "WARNING: This will delete all data in schema: $SchemaName" -ForegroundColor Red
        $confirmation = Read-Host "Type the schema name to confirm deletion"
        
        if ($confirmation -eq $SchemaName) {
            python scripts/schema_drop.py $SchemaName
        } else {
            Write-Host "Schema name confirmation failed. Aborted." -ForegroundColor Red
        }
    }
    
    "info" {
        Write-Host "Schema information:" -ForegroundColor Yellow
        python scripts/schema_info.py
    }
}

Write-Host "Schema management completed!" -ForegroundColor Green