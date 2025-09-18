# Database schema management script with new initialization system

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("create", "drop", "info", "init", "health", "repair")]
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
    
    "init" {
        Write-Host "Initializing database with new system..." -ForegroundColor Yellow
        python init_database.py
    }
    
    "health" {
        Write-Host "Checking database health..." -ForegroundColor Yellow
        python -c "
from app import create_app, db
from app.utils.database_initializer import DatabaseInitializer

app = create_app()
with app.app_context():
    initializer = DatabaseInitializer(app, db)
    result = initializer.validate_setup()
    
    if result.valid:
        print('✅ Database health check passed')
        if result.suggestions:
            print('💡 Suggestions:')
            for suggestion in result.suggestions:
                print(f'  💡 {suggestion}')
    else:
        print('❌ Database health check failed')
        if result.issues:
            print('❌ Issues:')
            for issue in result.issues:
                print(f'  ❌ {issue}')
        if result.suggestions:
            print('💡 Suggestions:')
            for suggestion in result.suggestions:
                print(f'  💡 {suggestion}')
"
    }
    
    "repair" {
        Write-Host "Attempting database repair..." -ForegroundColor Yellow
        python -c "
from app import create_app, db
from app.utils.database_initializer import DatabaseInitializer

app = create_app()
with app.app_context():
    initializer = DatabaseInitializer(app, db)
    result = initializer.repair_if_needed()
    
    if result.success:
        print('✅ Database repair completed successfully')
        if result.actions_taken:
            print('🔧 Actions taken:')
            for action in result.actions_taken:
                print(f'  🔧 {action}')
    else:
        print('❌ Database repair failed')
        if result.errors:
            print('❌ Errors:')
            for error in result.errors:
                print(f'  ❌ {error}')
"
    }
}

Write-Host "Schema management completed!" -ForegroundColor Green