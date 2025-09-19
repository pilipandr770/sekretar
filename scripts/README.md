# Scripts Directory

This directory contains essential management scripts for the AI Secretary application.

## Startup Scripts

### Local Development
```bash
# Start application for local development
python start.py
```

### Production (Render)
```bash
# Start application for production deployment
python start-prod.py
```

## Database Management

### Database Manager
```bash
# Interactive database management
python scripts/database_manager.py
```

### Schema Management
```bash
# Create database schema
python scripts/schema_create.py

# Drop database schema
python scripts/schema_drop.py

# Show schema information
python scripts/schema_info.py
```

### Key Generation
```bash
# Generate secure keys for production
python scripts/generate-keys.py
```

## PowerShell Scripts

### Database Operations
```powershell
# Database management commands
.\scripts\database-manager.ps1

# Initialize database
.\scripts\init-db.ps1

# Schema management
.\scripts\manage-schema.ps1
```

### Build and Deployment
```powershell
# Build for production
.\scripts\build-production.ps1

# Deploy to Render
.\scripts\deploy-render.ps1

# Environment validation
.\scripts\validate-env.ps1
```

### Translation Management
```powershell
# Extract translation messages
.\scripts\extract-messages.ps1

# Compile translations
.\scripts\compile-translations.ps1

# Update translations
.\scripts\update-translations.ps1

# Check translation status
.\scripts\translation-status.ps1

# Complete i18n workflow
.\scripts\i18n-workflow.ps1
```

### Development Tools
```powershell
# Setup development environment
.\scripts\setup.ps1

# Run tests
.\scripts\test.ps1

# Run Celery worker
.\scripts\run-celery.ps1
```

## Usage Guidelines

### For Local Development
1. Use `python start.py` for local development
2. The script will automatically:
   - Create .env file if missing
   - Set up required directories
   - Initialize database
   - Start the application

### For Production Deployment
1. Use `python start-prod.py` for production
2. Ensure all required environment variables are set
3. The script will:
   - Validate environment configuration
   - Apply database migrations
   - Check external service connectivity
   - Start the application

### Environment Variables
- Copy `.env.example` to `.env` for local development
- Set production environment variables in your deployment platform
- Use `scripts/generate-keys.py` to generate secure keys

### Database Setup
- Local development uses SQLite by default
- Production should use PostgreSQL
- Use database management scripts for maintenance

## Script Maintenance

This directory has been cleaned up to contain only essential scripts:
- Removed outdated startup scripts
- Consolidated functionality into main startup scripts
- Kept essential database and translation management tools

For any issues or questions, refer to the main project documentation.
